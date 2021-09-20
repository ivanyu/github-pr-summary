#!/usr/bin/env python
import argparse
import json
from datetime import datetime
from subprocess import check_output
from typing import Tuple, Dict, Any, List

from jinja2 import Environment, FileSystemLoader


PR = Dict[str, Any]


def fetch_prs(*, state: str, order_direction: str, repos: List[Tuple[str, str]]) -> List[PR]:
    query = """
      query ($org: String!, $name: String!, $state: PullRequestState!, $orderDirection: OrderDirection!) {
        repository(owner: $org, name: $name) {
          pullRequests(first: 100, states: [$state], orderBy: {field: CREATED_AT, direction: $orderDirection}) {
            nodes {
              title, url, createdAt, mergedAt, isDraft,
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
                               "-F", f"org={org}", "-F", f"name={repo}",
                               "-F", f"state={state}", "-F", f"orderDirection={order_direction}",
                               "-f", f"query={query}"])
        prs = json.loads(output)["data"]["repository"]["pullRequests"]["nodes"]
        result.extend(prs)

    result.sort(key=lambda pr: (pr["isDraft"], pr["createdAt"]))
    return result


def filter_prs(*, users: List[str], prs: List[PR]) -> List[PR]:
    if users:
        return [pr for pr in prs if pr["author"]["login"] in users]
    else:
        return prs


def keep_recently_merged(*, prs: List[PR], days: int) -> List[PR]:
    now = datetime.utcnow()
    result = []
    for pr in prs:
        merged_at = datetime.fromisoformat(pr["mergedAt"].rstrip("Z"))
        merged_days_ago = (now - merged_at).days
        if merged_days_ago < days:
            result.append(pr)
    return result


def enrich(*, prs: List[PR]) -> None:
    def days_to_string(days: int) -> str:
        if days == 0:
            return "recently"
        elif days % 10 == 1 and days != 11:
            return f"{days} day ago"
        else:
            return f"{days} days ago"

    now = datetime.utcnow()
    for pr in prs:
        created_at = datetime.fromisoformat(pr["createdAt"].rstrip("Z"))
        pr["createdStr"] = days_to_string((now - created_at).days)

        merged_at = pr.get("mergedAt")
        if merged_at is not None:
            merged_at = datetime.fromisoformat(merged_at.rstrip("Z"))
            pr["mergedStr"] = days_to_string((now - merged_at).days)


def render(*, open_prs: List[PR], merged_prs: List[PR]) -> str:
    env = Environment(loader=FileSystemLoader("."))
    tpl = env.get_template("template.html")
    return tpl.render(open_prs=open_prs, merged_prs=merged_prs, generated_at=datetime.utcnow())


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

    open_prs = fetch_prs(repos=args.repos, state="OPEN", order_direction="ASC")
    open_prs = filter_prs(users=args.users, prs=open_prs)
    enrich(prs=open_prs)

    merged_prs = fetch_prs(repos=args.repos, state="MERGED", order_direction="DESC")
    merged_prs = filter_prs(users=args.users, prs=merged_prs)
    merged_prs = keep_recently_merged(prs=merged_prs, days=3)
    enrich(prs=merged_prs)

    print(render(open_prs=open_prs, merged_prs=merged_prs))
