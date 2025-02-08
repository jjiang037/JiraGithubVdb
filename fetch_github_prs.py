import json
import requests
from github import Github

# Configuration
# For higher rate limits and private repos, set a valid GitHub personal access token.
# For public repositories and light use, you can leave it empty.
GITHUB_TOKEN = ''  # Replace with your token or leave as None for anonymous
GITHUB_REPO = 'apache/hive'  # Replace with the target GitHub repository

# Initialize GitHub client (authenticated if token is provided)
if GITHUB_TOKEN:
    gh = Github(GITHUB_TOKEN)
else:
    gh = Github()  # anonymous client, limited rate

# Get the repository object
repo = gh.get_repo(GITHUB_REPO)

def fetch_pr_patch(patch_url):
    """
    Fetch the raw patch content from the given patch URL.
    """
    try:
        response = requests.get(patch_url)
        if response.status_code == 200:
            return response.text
        else:
            return ""
    except Exception as e:
        print(f"Error fetching patch from {patch_url}: {e}")
        return ""

def fetch_github_pull_requests(repo, state='all', max_results=50):
    """
    Fetch pull requests from the GitHub repository.

    Args:
      repo: PyGithub Repository object.
      state: 'open', 'closed', or 'all'.
      max_results: Maximum number of PRs to fetch.

    Returns:
      List of dictionaries with PR details.
    """
    pull_requests = repo.get_pulls(state=state, sort='created', direction='desc')
    pr_list = []
    count = 0

    for pr in pull_requests:
        # Limit the number of PRs processed
        if count >= max_results:
            break

        # Fetch patch content using the patch URL
        patch_content = fetch_pr_patch(pr.patch_url)

        # Build the PR data record.
        pr_data = {
            "id": pr.number,
            "title": pr.title,
            "link": pr.html_url,
            "patch_url": pr.patch_url,
            "patch_content": patch_content,  # full patch content; might be large
            "body": pr.body,
            "state": pr.state,
            "created_at": pr.created_at.isoformat(),
            "merged": pr.merged,
            # Add any additional metadata as needed.
            "vector_db_metadata": {
                "github_pr_id": pr.number,
                "github_pr_link": pr.html_url,
                "patch_url": pr.patch_url
                # You can add more metadata fields here as required.
            }
        }
        pr_list.append(pr_data)
        count += 1

    return pr_list

if __name__ == '__main__':
    # Fetch pull requests from the repository.
    prs = fetch_github_pull_requests(repo, state='all', max_results=50)

    # Output the JSON so you can inspect it or store it in a file/database as needed.
    print(json.dumps(prs, indent=2))

    # ---
    # VECTOR DATABASE INTEGRATION SUGGESTIONS:
    #
    # 1. Choose a vector database:
    #    - Options include Pinecone, Weaviate, Milvus, or FAISS.
    #
    # 2. Generate embeddings:
    #    - Use an embedding model (e.g., OpenAI's embedding API, Sentence Transformers, etc.)
    #      to convert text (e.g., the PR title, body, or even the patch content) into embeddings.
    #
    # 3. Store metadata:
    #    - For each PR, store a document with:
    #         {
    #            "id": <unique identifier, e.g., github_pr_id>,
    #            "text": <text to embed, such as the PR title and/or patch content>,
    #            "metadata": {
    #                "github_pr_id": ...,
    #                "github_pr_link": ...,
    #                "source": "github"
    #            }
    #         }
    #
    # 4. Linking with other RAG systems:
    #    - When a query is made by your agent, generate an embedding for the query
    #      and search the vector database to retrieve relevant GitHub PRs.
    #    - The metadata (e.g., github_pr_link) can then be used to access the full details.
    #
    # 5. Implementation:
    #    - For example, using Pinecone:
    #         a. Create an index.
    #         b. Upsert your documents (each with an id, embedding vector, and metadata).
    #         c. Query the index by passing an embedding vector.
    #
    # The above script prepares your GitHub PR data with a "vector_db_metadata" field so that you
    # can later compute embeddings and insert them into your vector database for retrieval-augmented generation.
    # ---
