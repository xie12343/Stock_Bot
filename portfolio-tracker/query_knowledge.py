import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- 配置區 ---
DB_PATH = "./vector_db"              # 向量資料庫儲存路徑
EMBEDDING_MODEL = "BAAI/bge-m3" 

def query_knowledge(user_query: str):
    # 1. 初始化 Embedding 模型 (必須與 Ingest 時一致)
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'}
    )

    # 2. 載入已存在的向量資料庫
    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到向量資料庫: {DB_PATH}，請先執行 ingest_knowledge.py。")
        return

    vector_db = Chroma(
        persist_directory=DB_PATH,
        embedding_function=embeddings
    )

    # 3. 執行相似度檢索 (Similarity Search)
    print(f"🔍 正在檢索與『{user_query}』相關的知識...")
    results = vector_db.similarity_search(user_query, k=3) # 找出最相關的 3 個片段

    if not results:
        print("查無相關結果。")
    else:
        print("\n✨ 檢索結果：")
        for i, doc in enumerate(results):
            print(f"--- 來源片段 {i+1} ---")
            print(doc.page_content)
            print(f"來源: {doc.metadata.get('source', '未知')}\n")

if __name__ == "__main__":
    query = input("請輸入您的問題（例如：操作 SOP 或 基金報酬率）：")
    if query:
        query_knowledge(query)
