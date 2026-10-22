"""Bounded static configuration observations, without executing server configs.

Includes are resolved only within the standard server configuration tree. Dynamic
routes, overrides and application health remain explicitly unverified.
"""

import fnmatch
import posixpath
import re

from .models import ConfigRelation


class ConfigurationAdapter:
    name = "php-static-configuration-v2"

    def supports(self, environment):
        return environment.os_id in {"ubuntu", "debian"}

    def discover(self, collector, inventory):
        branches = sorted({p.source_name[3:] for p in inventory.packages
                           if re.fullmatch(r"php[0-9]+\.[0-9]+", p.source_name) and p.sapi == "fpm"})
        for branch in branches:
            root = f"/etc/php/{branch}/fpm"
            documents = self.tree(collector, inventory, root + "/php-fpm.conf", root, "fpm")
            pools = {}
            for path, raw, ident in documents:
                section = "global"
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith((";", "#")):
                        continue
                    if re.fullmatch(r"\[[A-Za-z0-9_.-]+\]", line):
                        section = line[1:-1]
                    elif "=" in line:
                        key, value = (v.strip() for v in line.split("=", 1))
                        if key == "listen" and section != "global":
                            ambiguous = section in pools or not re.fullmatch(r"/[A-Za-z0-9_./-]+|(?:127\.0\.0\.1|\[::1\]):[0-9]+", value)
                            if ambiguous:
                                inventory.coverage_gaps.append("FPM_POOL_LISTENER_AMBIGUOUS_OR_UNSUPPORTED")
                            pools[section] = value
                            inventory.config_relations.append(ConfigRelation(
                                "fpm_pool", path, section, value if not ambiguous else "UNRESOLVED",
                                "CONFIGURED_NOT_PROVEN_LOADED", tuple(d[2] for d in documents),
                                ("AMBIGUOUS_OR_UNSUPPORTED_LISTENER",) if ambiguous else ()))
                        if key in {"chroot", "include"} and (key == "chroot" or "$" in value):
                            inventory.coverage_gaps.append("FPM_DYNAMIC_OR_CHROOT_CONFIGURATION")
            if not pools:
                inventory.coverage_gaps.append(f"FPM_POOLS_UNRESOLVED:{branch}")
            # PHP extensions and per-pool directives can change loaded behavior.
        for branch, sapi in sorted({(p.source_name[3:], p.sapi) for p in inventory.packages
                                   if re.fullmatch(r"php[0-9]+\.[0-9]+", p.source_name)
                                   and p.sapi in {"fpm", "apache2", "cli", "cgi"}}):
            self.php_inputs(collector, inventory, f"/etc/php/{branch}/{sapi}")
        for root, initial, kind in (("/etc/nginx", "nginx.conf", "nginx"),
                                    ("/etc/apache2", "apache2.conf", "apache")):
            docs = self.tree(collector, inventory, f"{root}/{initial}", root, kind, optional=True)
            conditional = any(re.search(r"<(?:If\w*|Else)\b|\bif\s*\(", raw, re.I) for _, raw, _ in docs)
            if conditional:
                inventory.coverage_gaps.append("CONDITIONAL_WEB_CONFIGURATION_UNRESOLVED:" + root)
            for path, raw, ident in docs:
                for line in raw.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    match = re.search(r"\bfastcgi_pass\s+([^;\s]+)\s*;", stripped) if kind == "nginx" else re.search(r"\b(?:SetHandler|ProxyPassMatch|LoadModule)\s+(.+)", stripped, re.I)
                    if match:
                        target = match[1].strip('"')
                        # Keep only non-secret endpoint/module relations; never full config lines.
                        endpoint = re.search(r"unix:([/A-Za-z0-9_.-]+)|(/usr/lib/apache2/modules/libphp[0-9.]+\.so)|application/x-httpd-php", target)
                        target = endpoint[0] if endpoint else (target if re.fullmatch(r"(?:127\.0\.0\.1:[0-9]+|unix:/[A-Za-z0-9_./-]+)", target) else "UNRESOLVED")
                        inventory.config_relations.append(ConfigRelation(
                            "configured_web_handler", path, kind, target,
                            "CONFIGURED_ROUTE_ONLY", tuple(d[2] for d in docs),
                            ("CONDITIONAL_CONTEXT_UNRESOLVED",) if conditional else ()))
                        if target == "UNRESOLVED":
                            inventory.coverage_gaps.append("DYNAMIC_WEB_HANDLER_UNRESOLVED")
            if docs:
                inventory.coverage_gaps.append("HTTP_ROUTING_AND_OVERRIDES_REQUIRE_APPLICATION_PROBE")
        inventory.coverage_gaps.append("CONFIGURATION_NOT_PROVEN_LOADED_BY_RUNNING_SERVICE")

    def php_inputs(self, collector, inventory, root):
        raw, _ = collector.probe("read_text", root + "/php.ini")
        names, _ = collector.probe("listdir", root + "/conf.d")
        if raw is None or names is None:
            inventory.coverage_gaps.append("PHP_CONFIGURATION_UNREADABLE")
        for name in names or []:
            if name.endswith(".ini"):
                content, _ = collector.probe("read_text", root + "/conf.d/" + name)
                if content is None:
                    inventory.coverage_gaps.append("PHP_CONFIGURATION_UNREADABLE")

    def tree(self, collector, inventory, initial, root, kind, optional=False):
        documents, seen, active = [], set(), set()
        def visit(path, depth=0, missing_ok=False):
            normalized = posixpath.normpath(path)
            if not normalized.startswith(root + "/") or depth > 16 or normalized in active:
                inventory.coverage_gaps.append("CONFIG_INCLUDE_OUTSIDE_SCOPE_CYCLE_OR_LIMIT")
                return
            if normalized in seen:
                if kind == 'fpm': inventory.coverage_gaps.append('FPM_REPEATED_INCLUDE_REQUIRES_REVIEW')
                return
            if len(seen) >= 256:
                inventory.coverage_gaps.append("CONFIG_INCLUDE_OUTSIDE_SCOPE_CYCLE_OR_LIMIT")
                return
            seen.add(normalized)
            active.add(normalized)
            raw, ident = collector.probe("read_text", normalized)
            if raw is None:
                if not missing_ok or collector.evidence[-1].outcome != "FileNotFoundError":
                    inventory.coverage_gaps.append(f"CONFIG_UNREADABLE:{normalized}")
                active.remove(normalized)
                return
            documents.append((normalized, raw, ident))
            for line in raw.splitlines():
                pattern = r"^\s*include\s*=\s*(.*?)\s*$" if kind == "fpm" else r"^\s*include(?:optional)?\s+(.+?)\s*;?\s*$"
                match = re.match(pattern, line, re.I)
                if not match:
                    continue
                target = match[1].strip().rstrip(";").strip('"')
                if not re.fullmatch(r"[A-Za-z0-9_./*?-]+", target):
                    inventory.coverage_gaps.append("CONFIG_DYNAMIC_INCLUDE_UNRESOLVED")
                    continue
                if not target.startswith("/"):
                    target = root + "/" + target
                parent, leaf = posixpath.split(target)
                parent = posixpath.normpath(parent)
                if not (parent == root or parent.startswith(root + "/")) or "*" in parent or "?" in parent:
                    inventory.coverage_gaps.append("CONFIG_INCLUDE_OUTSIDE_SCOPE_CYCLE_OR_LIMIT")
                    continue
                if "*" in leaf or "?" in leaf:
                    names, _ = collector.probe("listdir", parent)
                    if names is None:
                        inventory.coverage_gaps.append(f"CONFIG_INCLUDE_DIRECTORY_UNREADABLE:{parent}")
                    for name in names or []:
                        if fnmatch.fnmatchcase(name, leaf):
                            visit(parent + "/" + name, depth + 1)
                else:
                    visit(target, depth + 1, "includeoptional" in line.lower())
            active.remove(normalized)
        visit(initial, missing_ok=optional)
        for path, raw, _ in documents:
            current, _ = collector.probe("read_text", path)
            if current != raw:
                inventory.coverage_gaps.append("CONFIG_CHANGED_DURING_SCAN:" + path)
        return documents
