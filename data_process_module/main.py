import json
from flask import Flask, request, jsonify, make_response
import requests
from flask_cors import CORS, cross_origin  # 導入 CORS
import chromadb
from apscheduler.schedulers.background import BackgroundScheduler

DB_PATH = './DB'
chroma_client = chromadb.PersistentClient(path = DB_PATH)
collection = chroma_client.get_or_create_collection(name="Documents")

app = Flask(__name__)
# 允許所有來自 localhost:3000 的請求
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

# 暫時使用陣列儲存
documents = []

def load_datas_from_file():
    """
    從 JSON 檔案中加載 documents 列表
    """
    try:
        with open('./documents/datas.json', 'r') as f:
            global documents
            documents = json.load(f)["document"]
        print("Documents loaded from file.")
        print(f'Documents: {documents}')
    except (FileNotFoundError, KeyError):
        print("No existing file or 'document' key not found. Starting with an empty list.")
        documents = []

def save_datas_to_file():
    """
    將 documents 列表存儲為 JSON 檔案
    """
    with open('./documents/datas.json', 'w') as f:
        json.dump({"document": documents}, f)
        # print("Documents saved to file.")

scheduler = BackgroundScheduler()
scheduler.add_job(func=save_datas_to_file, trigger='interval', minutes=1)
scheduler.start()

@app.route('/process', methods=['POST', 'OPTIONS'])
@cross_origin()
def process_input():
    """
    Process user input and return the response from the AI model.
    """

    if request.method == "OPTIONS": # CORS preflight
        return _build_cors_preflight_response()
    # 檢查是否有 'content'
    if not request.json or 'content' not in request.json:
        return jsonify({'error': 'missing content'}), 400

    user_content = request.json['content']
    print(f'Content: {user_content}')
    
    rag_result = collection.query(
        query_texts=[user_content],
        n_results=2
    )
    print(f'RAG Result: {rag_result["documents"]}')
    rag_content = "\n".join(rag_result["documents"][0])
    
    system_prompt = '''The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly. 
You should end your answer with +++.
Q:What is your name?+++
A:My name is LLM_TA+++
Q:'''

    prompt_data = {
        'prompt': rag_content + system_prompt + user_content + '+++\nA:',
        'n_predict': 1024,
        'stop': ['+++', 'Q:']
    }

    # 將資料 POST 到另一個本地伺服器
    response = requests.post('http://localhost:8080/completion', json=prompt_data)
    print(f'response: {response}')

    if response.status_code != 200:
        return jsonify({'error': 'failed to process data'}), 500

    response_content = response.json()['content']
    print(response_content)
    # 直接使用 jsonify 回傳結果到前端
    return jsonify({'content': response_content})

#####################
### Documents API ###
#####################

@app.route('/add_document', methods=['POST', 'OPTIONS'])
@cross_origin()
def add_document():
    """
    Add a document to the documents list.
    """
    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    # 檢查是否有 'content'
    if not request.json or 'content' not in request.json:
        return jsonify({'error': 'missing content'}), 400

    user_content = request.json['content']
    print(f'Content: {user_content}')
    
    collection.add(documents=user_content, ids=[user_content])
    
    return jsonify({'message': 'document added'})

@app.route('/get_documents', methods=['GET', 'OPTIONS'])
@cross_origin()
def get_documents():
    """
    Get all documents in the documents list.
    """

    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    
    results = collection.get()
    print(f'Results: {results}')
    return jsonify({'documents': results['documents']})

@app.route('/update_document', methods=['POST', 'OPTIONS'])
@cross_origin()
def update_document():
    """
    Update a document in the documents list.
    """

    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    # 檢查是否有 'content'
    if not request.json or 'new_content' not in request.json or 'old_content' not in request.json:
        return jsonify({'error': 'missing content'}), 400

    new_content = request.json['new_content']
    old_content = request.json['old_content']
    print(f'Old Content: {old_content}')
    print(f'New Content: {new_content}')
    
    collection.delete(ids=[old_content])
    collection.add(documents=new_content, ids=[new_content])
    
    return jsonify({'message': 'document updated'})

@app.route('/delete_document', methods=['POST', 'OPTIONS'])
@cross_origin()
def delete_document():
    """
    Delete a document from the documents list.
    """

    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    # 檢查是否有 'content'
    if not request.json or 'content' not in request.json:
        return jsonify({'error': 'missing content'}), 400

    user_content = request.json['content']
    print(f'Content: {user_content}')
    
    collection.delete(ids=[user_content])
    return jsonify({'message': 'document removed'})

@app.route('/clear_documents', methods=['GET', 'OPTIONS'])
@cross_origin()
def clear_documents():
    """
    Clear all documents from the documents list.
    """

    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    chroma_client.reset()
    return jsonify({'message': 'documents cleared'})

@app.route('/query_document', methods=['POST', 'OPTIONS'])
@cross_origin()
def query_document():
    """
    Query a document from the documents list.
    """

    if request.method == "OPTIONS":
        return _build_cors_preflight_response()
    # 檢查是否有 'content'
    if not request.json or 'content' not in request.json:
        return jsonify({'error': 'missing content'}), 400

    user_content = request.json['content']
    print(f'Content: {user_content}')
    results = collection.query(
        query_texts=[user_content],
        n_results=2
    )
    print(f'Results: {results}')
    
    return jsonify({'results': results})

def _build_cors_preflight_response():
    """
    Builds a CORS preflight response.
    """

    response = make_response()
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "*")
    response.headers.add("Access-Control-Allow-Methods", "*")
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)
