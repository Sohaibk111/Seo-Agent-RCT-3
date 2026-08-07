import re
from typing import Dict, Any, List, Optional

class RobotsRule:
    def __init__(self, user_agent: str):
        self.user_agent = user_agent.strip().lower()
        self.allow: List[str] = []
        self.disallow: List[str] = []
        self.crawl_delay: Optional[float] = None

class RobotsService:
    """
    Service to parse robots.txt contents and evaluate access permissions,
    crawl delays, and sitemap directives.
    """
    def __init__(self, content: str = ""):
        self.raw_content = content
        self.sitemaps: List[str] = []
        self.rules: Dict[str, RobotsRule] = {}
        if content:
            self.parse(content)

    def parse(self, content: str) -> None:
        self.raw_content = content
        self.sitemaps = []
        self.rules = {}

        current_agents: List[str] = []
        expecting_directives = False
        lines = content.splitlines()

        for raw_line in lines:
            line = raw_line.split('#')[0].strip()
            if not line or ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()

            if key == 'user-agent':
                agent = value.lower()
                if expecting_directives:
                    current_agents = [agent]
                    expecting_directives = False
                else:
                    if agent not in current_agents:
                        current_agents.append(agent)

                for ag in current_agents:
                    if ag not in self.rules:
                        self.rules[ag] = RobotsRule(ag)
            elif key == 'sitemap':
                if value and value not in self.sitemaps:
                    self.sitemaps.append(value)
            elif current_agents:
                expecting_directives = True
                for ag in current_agents:
                    rule = self.rules[ag]
                    if key == 'allow':
                        if value:
                            rule.allow.append(value)
                    elif key == 'disallow':
                        if value:
                            rule.disallow.append(value)
                    elif key == 'crawl-delay':
                        try:
                            rule.crawl_delay = float(value)
                        except ValueError:
                            pass

    def get_rule_for_agent(self, user_agent: str = "*") -> Optional[RobotsRule]:
        agent_lower = user_agent.lower()
        if agent_lower in self.rules:
            return self.rules[agent_lower]
        if "*" in self.rules:
            return self.rules["*"]
        return None

    def is_allowed(self, path: str, user_agent: str = "*") -> bool:
        rule = self.get_rule_for_agent(user_agent)
        if not rule:
            return True

        longest_match_len = -1
        allowed = True

        for dis in rule.disallow:
            if self._path_matches(path, dis):
                if len(dis) > longest_match_len:
                    longest_match_len = len(dis)
                    allowed = False

        for allow in rule.allow:
            if self._path_matches(path, allow):
                if len(allow) >= longest_match_len:
                    longest_match_len = len(allow)
                    allowed = True

        return allowed

    def get_crawl_delay(self, user_agent: str = "*") -> Optional[float]:
        rule = self.get_rule_for_agent(user_agent)
        return rule.crawl_delay if rule else None

    @staticmethod
    def _path_matches(path: str, pattern: str) -> bool:
        if not pattern:
            return False
        regex_pattern = re.escape(pattern).replace(r'\*', '.*')
        if regex_pattern.endswith(r'\$'):
            regex_pattern = regex_pattern[:-2] + '$'
        else:
            regex_pattern = '^' + regex_pattern

        return bool(re.search(regex_pattern, path))

    def to_dict(self, user_agent: str = "*") -> Dict[str, Any]:
        rule = self.get_rule_for_agent(user_agent)
        return {
            "sitemaps": self.sitemaps,
            "userAgent": user_agent,
            "crawlDelay": rule.crawl_delay if rule else None,
            "allow": rule.allow if rule else [],
            "disallow": rule.disallow if rule else [],
            "rules": {
                ag: {
                    "userAgent": r.user_agent,
                    "allow": r.allow,
                    "disallow": r.disallow,
                    "crawlDelay": r.crawl_delay
                }
                for ag, r in self.rules.items()
            }
        }
