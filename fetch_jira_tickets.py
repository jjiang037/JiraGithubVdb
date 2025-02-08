import json
import re
from jira import JIRA

# Configuration
JIRA_URL = 'https://issues.apache.org/jira'  # Replace with your Jira URL
GITHUB_REPO = 'apache/hive'  # Replace with the target GitHub repository (e.g., 'apache/spark')
JIRA_PROJECT_KEY = 'HIVE'  # Replace with the target Jira project key (e.g., 'SPARK')

# Initialize Jira client (no authentication required for public Jira instances)
jira = JIRA(server=JIRA_URL)

def clean_text(text):
    """
    Clean up text by removing unwanted characters, extra spaces, and formatting issues.
    If text is None, return an empty string.
    """
    if not text:
        return ""

    # Remove extra whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove special characters (e.g., \u00a0 for non-breaking space)
    text = text.replace('\u00a0', ' ')

    # Remove HTML tags (if any)
    text = re.sub(r'<[^>]+>', '', text)

    # Remove Jira markup (e.g., {code}, {noformat})
    text = re.sub(r'\{.*?\}', '', text)

    # Remove redundant spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text

def extract_github_info(text, github_repo):
    """
    Extract GitHub commit and PR URLs from text for a given GitHub repository.
    Handles both direct URLs and Jira-formatted links.
    """
    # Updated regex: allow 7 to 40 hexadecimal characters for commit hashes
    commit_pattern = rf'\[[^|]+\|(https://github\.com/{re.escape(github_repo)}/commit/[a-f0-9]{{7,40}})\]|(https://github\.com/{re.escape(github_repo)}/commit/[a-f0-9]{{7,40}})'
    # Regex to match GitHub PR URLs (direct or Jira-formatted)
    pr_pattern = rf'\[[^|]+\|(https://github\.com/{re.escape(github_repo)}/pull/\d+)\]|(https://github\.com/{re.escape(github_repo)}/pull/\d+)'

    # Find all matches for commits
    commit_matches = re.findall(commit_pattern, text, flags=re.IGNORECASE)
    commits = [match[0] or match[1] for match in commit_matches if match[0] or match[1]]

    # Find all matches for PRs
    pr_matches = re.findall(pr_pattern, text)
    prs = [match[0] or match[1] for match in pr_matches if match[0] or match[1]]

    return {
        'commits': commits,
        'prs': prs
    }

def extract_jira_links(text):
    """
    Extract Jira ticket links from text.
    For example: https://issues.apache.org/jira/browse/HIVE-28723
    """
    jira_link_pattern = r'(https://issues\.apache\.org/jira/browse/[A-Z]+-\d+)'
    return re.findall(jira_link_pattern, text)

def fetch_jira_issues(jira_project_key, github_repo):
    """
    Fetch Jira issues for a given project and extract associated GitHub PRs, commits,
    and also capture Jira links found in the issue description.
    """
    # JQL query to fetch issues from the specified project
    jql = f'project = {jira_project_key} ORDER BY created DESC'

    # Fetch issues (maxResults can be adjusted)
    issues = jira.search_issues(jql, maxResults=50, expand='issuelinks')

    results = []

    for issue in issues:
        # Clean up the description (ensuring it returns a string)
        cleaned_description = clean_text(issue.fields.description)
        github_info_from_desc = extract_github_info(cleaned_description, github_repo)
        jira_links_from_desc = extract_jira_links(cleaned_description)

        issue_data = {
            'key': issue.key,
            'title': issue.fields.summary,
            'created': issue.fields.created,
            'description': cleaned_description,
            'status': issue.fields.status.name,
            'components': [c.name for c in issue.fields.components],
            'fix_versions': [v.name for v in issue.fields.fixVersions],
            'comments': [],
            # Include both GitHub and (if any) Jira-related links from the description
            'github_related_pr': {
                'commits': github_info_from_desc['commits'],
                'prs': github_info_from_desc['prs'],
                'jira_links': jira_links_from_desc
            },
            # For vector db linking, we also store the Jira ticket number here
            'vector_db_metadata': {
                'jira_ticket': issue.key,
                'github_urls': []  # This will be populated from comments and issuelinks
            }
        }

        # Process comments: extract cleaned text and GitHub info
        if issue.fields.comment and issue.fields.comment.comments:
            for comment in issue.fields.comment.comments:
                cleaned_comment_body = clean_text(comment.body)
                issue_data['comments'].append({
                    'author': comment.author.displayName,
                    'body': cleaned_comment_body,
                    'created': comment.created
                })

                # Extract GitHub info from comment text
                github_info = extract_github_info(comment.body, github_repo)
                issue_data['github_related_pr']['commits'].extend(github_info['commits'])
                issue_data['github_related_pr']['prs'].extend(github_info['prs'])
                # Optionally, add any GitHub URLs to the vector metadata
                issue_data['vector_db_metadata']['github_urls'].extend(
                    github_info['commits'] + github_info['prs']
                )

        # Process issue links (e.g., Jira links that refer to GitHub PRs)
        if hasattr(issue.fields, 'issuelinks'):
            for link in issue.fields.issuelinks:
                if hasattr(link, 'outwardIssue'):
                    # Check if the link is a GitHub PR by looking in its summary
                    if hasattr(link.outwardIssue.fields, 'summary'):
                        if 'GitHub Pull Request' in link.outwardIssue.fields.summary:
                            # Extract PR URL from the summary
                            pr_match = re.search(r'https://github\.com/[^/]+/[^/]+/pull/\d+', link.outwardIssue.fields.summary)
                            if pr_match:
                                pr_url = pr_match.group(0)
                                issue_data['github_related_pr']['prs'].append(pr_url)
                                issue_data['vector_db_metadata']['github_urls'].append(pr_url)

        # Remove duplicates from commits, PRs, and GitHub URLs
        issue_data['github_related_pr']['commits'] = list(set(issue_data['github_related_pr']['commits']))
        issue_data['github_related_pr']['prs'] = list(set(issue_data['github_related_pr']['prs']))
        issue_data['github_related_pr']['jira_links'] = list(set(issue_data['github_related_pr']['jira_links']))
        issue_data['vector_db_metadata']['github_urls'] = list(set(issue_data['vector_db_metadata']['github_urls']))

        results.append(issue_data)

    return results

if __name__ == '__main__':
    # Fetch issues for the specified Jira project and GitHub repository
    issues = fetch_jira_issues(JIRA_PROJECT_KEY, GITHUB_REPO)
    # Output the JSON so you can inspect it, or store it in a file/database as needed
    print(json.dumps(issues, indent=2))

    # ---
    # VECTOR DATABASE INTEGRATION SUGGESTIONS:
    #
    # 1. Choose a vector database:
    #    - Options include Pinecone, Weaviate, Milvus, or FAISS.
    #
    # 2. Generate embeddings:
    #    - Use an embedding model (e.g., OpenAI's embedding API, Sentence Transformers, etc.)
    #      to convert your text (e.g., issue description, comment bodies, GitHub URLs) into embeddings.
    #
    # 3. Store metadata:
    #    - For Jira, you can store the Jira ticket number (issue_data['key']) along with its embedding.
    #    - For GitHub information, store each commit or PR URL along with its embedding.
    #    - You can structure your document such that each record has:
    #         {
    #            "id": <unique identifier>,
    #            "text": <text to embed>,
    #            "metadata": {
    #                "jira_ticket": ...,
    #                "github_url": ...,
    #                "source": "jira" or "github"
    #            }
    #         }
    #
    # 4. Linking the two RAG systems:
    #    - When querying one system (say, you query a Jira ticket), you retrieve its embedding,
    #      then search the GitHub vector index for embeddings that are similar.
    #    - Alternatively, if you have a unified vector store, you can index both types of documents together,
    #      and your query can retrieve related Jira issues and GitHub commits/PRs in one step.
    #
    # 5. Querying:
    #    - Your agent can generate an embedding from a query (or context)
    #      and search the vector DB to retrieve relevant Jira issues or GitHub artifacts.
    #    - Based on the metadata (e.g., jira_ticket, github_url) in the returned documents,
    #      you can then cross-reference the information.
    #
    # 6. Implementation:
    #    - For example, if using Pinecone:
    #         a. Create an index.
    #         b. Upsert your documents (each with an id, embedding vector, and metadata).
    #         c. Query the index by passing an embedding vector.
    #
    # The above script prepares your data with the necessary fields (like 'vector_db_metadata') so you can
    # later loop over these records to compute embeddings and insert them into your vector DB of choice.
    #
    # You can modify and expand this integration based on your specific vector DB and embedding model.
    # ---
