from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from .repo_walk import create_metadata_tree
import openai
import pdb

app = FastAPI()
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

class RepoRequest(BaseModel):
    repo_name: str

@app.on_event("startup")
async def startup_event():
    global qdrant_client
    qdrant_client = QdrantClient(host="localhost", port=6333)
    print("Connected to Qdrant")

# Check if collection (repo) exists
@app.get("/repo/{repo_name}")
async def check_repo_exists(repo_name: str):
    try:
    
        
        collection_info = qdrant_client.get_collection(repo_name)
        return {"message": f"Repository '{repo_name}' exists."}
    except Exception:
        return {"message": f"Repository '{repo_name}' does not exist."}

# Create collection (repo) with POST request
@app.post("/repo")
async def create_repo(repo_request: RepoRequest):
    try:
        repo_name = repo_request.repo_name  # Extract the repo_name from the request object

        # Delete the existing collection if it exists
        try:
            qdrant_client.delete_collection(repo_name)
        except Exception:
            pass  # Collection might not exist, ignore

        # Create a new collection with the correct vector size (384)
        qdrant_client.create_collection(
            collection_name=repo_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE)  # Use 384 for this model
        )
        return {"message": f"Repository '{repo_name}' created with vector size 384"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Function to encode content into vectors
def encode_content(content: str):
    return model.encode(content).tolist()  # Convert to a list for Qdrant

def encode_as_vector(content):
    return model.encode(content)

# Insert vectors into repository
@app.post("/insert-vectors/{repo_name}")
async def insert_vectors(repo_name: str):
    try:
        # Generate your file, folder, and line metadata
        files_hash, folders_hash, lines_hash = create_metadata_tree(f"../readme-bot")

        # Prepare points to insert into Qdrant
        points = []
        id_counter = 0

        # Insert file vectors
        for file_path, file_metadata in files_hash.items():
            vector = encode_content(file_metadata["file_content"])
            points.append(
                PointStruct(
                    id=id_counter,
                    vector=vector,
                    payload={
                        "type": "file",
                        "file_path": file_path,
                        "metadata": file_metadata["metadata"]
                    }
                )
            )
            id_counter += 1

        # Insert folder vectors
        for folder_path, folder_metadata in folders_hash.items():
            vector = encode_content(folder_metadata["folder_content_summary"])
            points.append(
                PointStruct(
                    id=id_counter,
                    vector=vector,
                    payload={
                        "type": "folder",
                        "folder_path": folder_path,
                        "files": folder_metadata["files"]
                    }
                )
            )
            id_counter += 1

        # Insert line vectors
        for line_key, line_metadata in lines_hash.items():
            vector = encode_content(line_metadata["line_content"])
            points.append(
                PointStruct(
                    id=id_counter,
                    vector=vector,
                    payload={
                        "type": "line",
                        "file_path": line_metadata["file_path"],
                        "line_number": line_metadata["line_number"],
                        "surrounding_context": line_metadata["surrounding_context"]
                    }
                )
            )
            id_counter += 1

        # Upsert points into Qdrant collection
        qdrant_client.upsert(
            collection_name=repo_name,
            points=points
        )
        return {"message": f"{len(points)} vectors inserted into '{repo_name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Function to get OpenAI embedding for the query
def get_openai_embedding(query: str):
    response = openai.Embedding.create(
        input=query,
        model="text-embedding-ada-002"
    )
    embedding = response['data'][0]['embedding']
    return embedding

# Function to retrieve surrounding lines for context
def get_context(payload):
    surrounding_context = payload.get("surrounding_context", [])
    return [context for context in surrounding_context if context]

# Search endpoint that retrieves the top 20 similar vectors
@app.post("/search/{repo_name}")
async def search_vectors(repo_name: str, query: str, top_k: int = 20):
    try:
        
        # Get OpenAI embedding for the query
        
        query_vector = encode_as_vector(query)

        # Search for top-k similar vectors in Qdrant
        search_results = qdrant_client.search(
            collection_name=repo_name,
            query_vectors=[query_vector],
            limit=top_k
        )

        # Process search results
        results_with_context = []
        for result in search_results:
            payload = result.payload
            results_with_context.append({
                "score": result.score,
                "type": payload["type"],
                "path": payload.get("file_path", payload.get("folder_path")),
                "line_number": payload.get("line_number"),
                "line_content": payload.get("line_content"),
                "context": get_context(payload),
                "directory": payload.get("folder_path"),
                "metadata": payload.get("metadata")
            })

        return {"results": results_with_context}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))