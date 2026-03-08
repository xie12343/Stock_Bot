import os
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# --- 配置區 ---
PDF_KNOWLEDGE_PATH = "./pdf_sop_base"  # 存放 PDF SOP 的目錄
DB_PATH = "./vector_db"                # 向量資料庫儲存路徑（可與 MD 共用）
EMBEDDING_MODEL = "BAAI/bge-m3"        # 支援多語系的嵌入模型

def ingest_pdf_documents():
    # 1. 讀取目錄下所有 PDF 文件
    print(f"📄 開始掃描 PDF 目錄: {PDF_KNOWLEDGE_PATH} ...")
    
    # 檢查是否有 .pdf 檔案
    import glob
    if not glob.glob(os.path.join(PDF_KNOWLEDGE_PATH, "**/*.pdf"), recursive=True):
        print(f"⚠️ {PDF_KNOWLEDGE_PATH} 中沒有發現任何 .pdf 文件，跳過讀取。")
        return

    # 使用 PyPDFLoader 處理每一頁
    loader = DirectoryLoader(
        PDF_KNOWLEDGE_PATH, 
        glob="**/*.pdf", 
        loader_cls=PyPDFLoader
    )
    
    documents = loader.load()
    print(f"✅ 已讀取 {len(documents)} 頁內容。")

    # 2. PDF 特殊分塊策略 (PDF Chunking)
    # PDF 容易在換頁時斷掉語意，因此 chunk_overlap (重疊區) 要設大一點
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,        # PDF 資訊密度較低，建議設大一點
        chunk_overlap=200,      # 增加重疊，防止指令或專有名詞被截斷
        separators=["\n\n", "\n", "。", " ", ""] 
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"✂️ PDF 已切分為 {len(chunks)} 個知識塊。")
    if not chunks:
        print("⚠️ 沒有發現任何有效的 PDF 知識塊，跳過向量化。")
        return

    # 3. 初始化 Embedding 模型
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'} 
    )

    # 4. 存入或更新 ChromaDB
    # 注意：這裡使用跟 MD 相同的 DB_PATH，AI 就能同時檢索 MD 與 PDF
    print(f"📦 正在將 PDF 知識存入向量資料庫...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_PATH
    )
    
    print("✨ PDF 向量化完成！現在 RAG 系統已包含 PDF 內容。")

if __name__ == "__main__":
    # 確保目錄存在且含有 .pdf 檔案
    import glob
    has_pdf = glob.glob(os.path.join(PDF_KNOWLEDGE_PATH, "**/*.pdf"), recursive=True)

    if not os.path.exists(PDF_KNOWLEDGE_PATH):
        os.makedirs(PDF_KNOWLEDGE_PATH)
        print(f"📁 已建立目錄 {PDF_KNOWLEDGE_PATH}。請放入 PDF SOP 文件後重新執行。")
    elif not has_pdf:
        print(f"⚠️ {PDF_KNOWLEDGE_PATH} 目錄存在但沒有發現任何 .pdf 文件，請放入文件後重新執行。")
    else:
        ingest_pdf_documents()