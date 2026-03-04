import os
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- 配置區 ---
KNOWLEDGE_PATH = "./knowledge_base"  # 你的 Markdown SOP 目錄
DB_PATH = "./vector_db"              # 向量資料庫儲存路徑
# 建議使用 BGE-M3 模型，對中文與技術指令理解力最強
EMBEDDING_MODEL = "BAAI/bge-m3" 

def ingest_sop_documents():
    # 1. 讀取目錄下所有 Markdown 文件
    print(f"🚀 開始讀取目錄: {KNOWLEDGE_PATH} ...")
    
    # 檢查是否有 .md 檔案
    import glob
    if not glob.glob(os.path.join(KNOWLEDGE_PATH, "**/*.md"), recursive=True):
        print(f"⚠️ {KNOWLEDGE_PATH} 中沒有發現任何 .md 文件，跳過讀取。")
        return

    loader = DirectoryLoader(
        KNOWLEDGE_PATH, 
        glob="**/*.md", 
        loader_cls=UnstructuredMarkdownLoader
    )
    documents = loader.load()
    print(f"✅ 已讀取 {len(documents)} 份文件。")

    # 2. 文件分塊 (Chunking)
    # 針對 SOP 格式，建議 chunk_size 設為 500-800，確保指令塊不會被切斷
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✂️ 文件已切分為 {len(chunks)} 個知識塊。")
    # 這裡的 chunks 是針對「已讀取文件」的切分結果

    # 3. 初始化 Embedding 模型
    print(f"🧬 正在加載 Embedding 模型: {EMBEDDING_MODEL} ...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'} # 若有 GPU 可改為 'cuda'
    )

    # 4. 存入 ChromaDB 向量資料庫
    print(f"📦 正在將知識塊存入向量資料庫 ({DB_PATH}) ...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    print("✨ 向量化完成！現在 AI 可以檢索你的 SOP 知識庫了。")

if __name__ == "__main__":
    # 確保目錄存在且含有 .md 檔案
    import glob
    has_md = glob.glob(os.path.join(KNOWLEDGE_PATH, "**/*.md"), recursive=True)
    
    if not os.path.exists(KNOWLEDGE_PATH):
        os.makedirs(KNOWLEDGE_PATH)
        print(f"📁 已建立目錄 {KNOWLEDGE_PATH}。請放入 Markdown SOP 文件後重新執行。")
    elif not has_md:
        print(f"⚠️ {KNOWLEDGE_PATH} 目錄存在但沒有發現任何 .md 文件，請放入文件後重新執行。")
    else:
        ingest_sop_documents()