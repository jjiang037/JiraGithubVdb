from jira import JIRA

JIRA_SERVER = "https://your-jira-instance.atlassian.net"
JIRA_USER = "your-email@example.com"
JIRA_API_TOKEN = "your-api-token"

def get_jira_issues(jql_query="project=YOUR_PROJECT AND status='Done'"):
    options = {"server": JIRA_SERVER}
    jira = JIRA(options, basic_auth=(JIRA_USER, JIRA_API_TOKEN))

    issues = jira.search_issues(jql_query, maxResults=10)
    extracted_issues = []

    for issue in issues:
        data = {
            "key": issue.key,
            "start_date": issue.fields.created,
            "description": issue.fields.description,
            "comments": [comment.body for comment in jira.comments(issue.key)],
        }
        extracted_issues.append(data)

    return extracted_issues





# See PyCharm help at https://www.jetbrains.com/help/pycharm/
