#!/usr/bin/env python
import argparse
import json
from datetime import datetime
from subprocess import check_output
from typing import Tuple, Dict, Any, List

from jinja2 import Environment, FileSystemLoader


PR = Dict[str, Any]


def fetch_prs(*, repos: List[Tuple[str, str]]) -> List[PR]:
    query = """
        query ($org: String!, $name: String!) {
          repository(owner: $org, name: $name) {
            pullRequests(first: 100, states: OPEN, orderBy: {field: CREATED_AT, direction: ASC}) {
              nodes {
                title, url, createdAt, isDraft,
                author {
                  ... on User {
                    login, name, avatarUrl
                  }
                }
              }
            }
          }
        }
    """
    result = []
    for org, repo in repos:
        output = check_output(["gh", "api", "graphql", "--paginate",
                               "-F", f"org={org}", "-F", f"name={repo}", "-f", f"query={query}"])
        prs = json.loads(output)["data"]["repository"]["pullRequests"]["nodes"]
        result.extend(prs)

    result.sort(key=lambda pr: (pr["isDraft"], pr["createdAt"]))
    return result


def filter_prs(*, users: List[str], prs: List[PR]) -> List[PR]:
    if users:
        return [pr for pr in prs if pr["author"]["login"] in users]
    else:
        return prs


def enrich(*, prs: List[PR]) -> None:
    now = datetime.now()
    for pr in prs:
        created_at = datetime.fromisoformat(pr["createdAt"].rstrip("Z"))
        created_days_ago = (now - created_at).days
        if created_days_ago == 0:
            pr["createdStr"] = "recently"
        elif created_days_ago % 10 == 1 and created_days_ago != 11:
            pr["createdStr"] = f"{created_days_ago} day ago"
        else:
            pr["createdStr"] = f"{created_days_ago} days ago"


def render(*, prs: List[PR]) -> str:
    env = Environment(loader=FileSystemLoader("."))
    tpl = env.get_template("template.html")
    return tpl.render(prs=prs)


if __name__ == "__main__":
    def parse_repo(repo_str: str) -> Tuple[str, str]:
        r = repo_str.split("/")
        if len(r) != 2 or len(r[0]) == 0 or len(r[1]) == 0:
            raise ValueError()
        return r[0], r[1]

    parser = argparse.ArgumentParser()
    parser.add_argument("--repos", type=parse_repo, metavar="REPO", nargs='+', required=False,
                        help='repositories to look at: org/repo')
    parser.add_argument("--users", type=str, metavar="USER", nargs='*', required=False,
                        help='users to look at')

    args = parser.parse_args()

    prs = fetch_prs(repos=args.repos)
    prs = filter_prs(users=args.users, prs=prs)
    enrich(prs=prs)
    print(render(prs=prs))
