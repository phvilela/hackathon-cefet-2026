#!/usr/bin/env python3
"""plaky.py — CLI minimalista para a API pública do Plaky (somente stdlib).

Autenticação via variável de ambiente (nunca hardcode a key):
    export PLAKY_API_KEY="plk_..."

Exemplos:
    python3 plaky.py me
    python3 plaky.py boards
    python3 plaky.py items --board EMB --status "A fazer"
    python3 plaky.py search --board CE --query "deploy"
    python3 plaky.py create --board EMB --group TT&C --title "Revisar doc" \\
        --assignee gabrielmoura0282@gmail.com --due 2026-10-10 --status "A fazer"
    python3 plaky.py set-field --board EMB 7512057 Status "Em progresso"
    python3 plaky.py comment --board EMB 7512057 --text "Verificado no DP"
    python3 plaky.py move --board EMB 7512057 --group OBC
    python3 plaky.py delete --board EMB 7512057 --yes
    python3 plaky.py upload --board EMB 7512057 --file ./doc.pdf

Boards (atalhos): EMB MEC ADM CE PED  (P&D = PED)
Flags globais: --json (saída bruta), --dry-run (mostra request sem enviar, só escrita)
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

BASE = "https://api.plaky.com/v1/public"
DEFAULT_SPACE = int(os.environ.get("PLAKY_SPACE_ID", "226365"))
BOARDS = {
    "EMB": 281389,   # Embarcados
    "MEC": 281391,   # Mecânica
    "ADM": 281390,   # Administração
    "CE": 281392,    # Controle & Energia
    "PED": 290488,   # Pesquisa & Desenvolvimento (P&D)
}
MAX_RETRIES = 3

# Apelidos PT-BR para as keys de campo (os boards do CEFAST usam títulos nulos;
# a API só aceita a key nesses casos). Ex.: Status -> status-1.
FIELD_ALIASES = {
    "status": "status-1",
    "prioridade": "status-2",
    "priority": "status-2",
    "responsavel": "person-1",
    "responsável": "person-1",
    "assignee": "person-1",
    "prazo": "date_time-1",
    "data": "date_time-1",
    "due": "date_time-1",
}


def resolve_field(client, space_id, board_id, name):
    """Traduz apelido/título para a key real do campo no board."""
    key = FIELD_ALIASES.get(str(name).strip().lower(), name)
    try:
        b = client.board_details(space_id, board_id)
        known = {(f.get("key") or "").lower() for f in b.get("fields", [])}
        known |= {(f.get("title") or "").lower() for f in b.get("fields", [])}
        if str(key).lower() not in known and str(name).lower() not in known:
            print(f"AVISO: campo '{name}' não existe no board {board_id}; tentando mesmo assim.",
                  file=sys.stderr)
    except PlakyError:
        pass
    return key


class PlakyError(Exception):
    pass


class PlakyClient:
    def __init__(self, api_key=None, dry_run=False):
        self.api_key = api_key or os.environ.get("PLAKY_API_KEY", "")
        if not self.api_key:
            raise PlakyError("PLAKY_API_KEY não definida. Exporte: export PLAKY_API_KEY=\"plk_...\"")
        self.dry_run = dry_run

    def _request(self, method, path, query=None, body=None, raw_bytes=None, content_type="application/json"):
        url = BASE + path
        if query:
            url += "?" + urllib.parse.urlencode(query, doseq=True)
        data = None
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        if raw_bytes is not None:
            data = raw_bytes
            headers["Content-Type"] = content_type
        elif body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.dry_run and method in ("POST", "PATCH", "PUT", "DELETE"):
            print(f"[dry-run] {method} {url}")
            if data:
                print(data.decode("utf-8", "replace")[:2000])
            return {"dry_run": True}
        for attempt in range(MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8")
                    return json.loads(text) if text else {}
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", "replace")[:1000]
                if e.code == 429 and attempt < MAX_RETRIES:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise PlakyError(f"HTTP {e.code} em {method} {path}: {err_body}")
            except urllib.error.URLError as e:
                raise PlakyError(f"Erro de rede em {method} {path}: {e}")

    def get(self, path, query=None):
        return self._request("GET", path, query)

    def post(self, path, body):
        return self._request("POST", path, body=body)

    def patch(self, path, body):
        return self._request("PATCH", path, body=body)

    def delete(self, path):
        return self._request("DELETE", path)

    def paged(self, path, query=None, max_pages=20):
        """Segue hasMore até o fim. Retorna lista acumulada."""
        out, page = [], 1
        query = dict(query or {})
        while page <= max_pages:
            query["page"] = page
            resp = self._request("GET", path, query)
            out.extend(resp.get("data", []))
            if not resp.get("hasMore"):
                break
            page += 1
        return out

    # ---- descoberta ----
    def me(self):
        return self.get("/users/me")

    def spaces(self):
        return self.paged("/spaces", {"pageSize": 50})

    def boards(self, space_id):
        return self.paged(f"/spaces/{space_id}/boards", {"pageSize": 50})

    def board_details(self, space_id, board_id):
        return self.get(f"/spaces/{space_id}/boards/{board_id}")

    def groups(self, space_id, board_id):
        return self.paged(f"/spaces/{space_id}/boards/{board_id}/item-groups", {"pageSize": 50})

    # ---- itens ----
    def items(self, space_id, board_id, page_size=50, max_pages=5, expand="fields,group", **filters):
        q = {"pageSize": page_size, "expand": expand}
        q.update({k: v for k, v in filters.items() if v is not None})
        return self.paged(f"/spaces/{space_id}/boards/{board_id}/items", q, max_pages=max_pages)

    def item(self, space_id, board_id, item_id, expand="fields,group"):
        return self.get(f"/spaces/{space_id}/boards/{board_id}/items/{item_id}",
                        {"expand": expand} if expand else None)

    def create_item(self, space_id, board_id, title=None, group=None, assignee_emails=(),
                    due=None, status=None, fields=None, subitem_of=None):
        body = {}
        if title:
            body["title"] = title
        if subitem_of:
            body["parentId"] = int(subitem_of)
        if group:
            if str(group).isdigit():
                body["groupId"] = int(group)
            else:
                body["groupTitle"] = group
        f = dict(fields or {})
        if status:
            f["status-1"] = status
        if due:
            f["date_time-1"] = normalize_date(due)
        if assignee_emails:
            users = self.users_by_email(list(assignee_emails))
            missing = set(assignee_emails) - {u["email"] for u in users}
            if missing:
                raise PlakyError(f"Usuários não encontrados no workspace: {sorted(missing)}")
            f["person-1"] = {"users": [{"id": u["id"]} for u in users]}
        if f:
            body["fields"] = f
        return self.post(f"/spaces/{space_id}/boards/{board_id}/items", body)

    def set_field(self, space_id, board_id, item_id, field, value):
        return self.patch(
            f"/spaces/{space_id}/boards/{board_id}/items/{item_id}/fields/{field}",
            {"value": value})

    def move_item(self, space_id, board_id, item_id, group_id):
        return self.patch(
            f"/spaces/{space_id}/boards/{board_id}/items/{item_id}/group",
            {"itemGroupId": int(group_id)})

    def delete_item(self, space_id, board_id, item_id):
        return self.delete(f"/spaces/{space_id}/boards/{board_id}/items/{item_id}")

    def comment(self, space_id, board_id, item_id, text):
        return self.post(
            f"/spaces/{space_id}/boards/{board_id}/items/{item_id}/comments",
            {"text": text})

    def upload(self, space_id, board_id, item_id, filepath):
        with open(filepath, "rb") as fh:
            content = fh.read()
        boundary = "----plakyboundary"
        name = os.path.basename(filepath)
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"{name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode()
        tail = f"\r\n--{boundary}--\r\n".encode()
        return self._request("POST",
                             f"/spaces/{space_id}/boards/{board_id}/items/{item_id}/files",
                             raw_bytes=head + content + tail,
                             content_type=f"multipart/form-data; boundary={boundary}")

    def users_by_email(self, emails):
        resp = self.get("/users", {"emails": emails, "pageSize": 50})
        return resp.get("data", [])


def normalize_date(s):
    s = s.strip()
    if len(s) == 10:  # YYYY-MM-DD
        return s + "T00:00:00-03:00"
    return s


def resolve_board(name_or_id):
    if name_or_id is None:
        raise PlakyError("Informe --board (EMB|MEC|ADM|CE|PED ou ID)")
    key = str(name_or_id).upper()
    if key in BOARDS:
        return BOARDS[key]
    if str(name_or_id).isdigit():
        return int(name_or_id)
    raise PlakyError(f"Board desconhecido: {name_or_id}. Use EMB|MEC|ADM|CE|PED ou o ID numérico.")


def resolve_group(client, space_id, board_id, name_or_id):
    if name_or_id is None:
        return None
    if str(name_or_id).isdigit():
        return int(name_or_id)
    for g in client.groups(space_id, board_id):
        if g["title"].lower() == str(name_or_id).lower():
            return g["id"]
    raise PlakyError(f"Grupo '{name_or_id}' não encontrado no board {board_id}.")


def field_value(item, key):
    for f in item.get("fields", []) or []:
        if f.get("key") == key or (f.get("title") or "").lower() == key.lower():
            return f.get("value")
    return None


def fmt_label(v):
    if isinstance(v, dict):
        return v.get("label", json.dumps(v, ensure_ascii=False))
    return v if v is not None else "-"


def fmt_person(v):
    if not isinstance(v, dict):
        return "-"
    users = v.get("assignedUsers") or v.get("users") or []
    return ",".join(u.get("name") or u.get("email", "?") for u in users) or "-"


def print_items(items, groups=None):
    gmap = {g["id"]: g["title"] for g in (groups or [])}
    print(f"{'ID':<10}{'GRUPO':<12}{'STATUS':<14}{'RESPONSÁVEL':<24}{'PRAZO':<12}TÍTULO")
    for i in items:
        gid = i.get("group")
        gid = gid.get("id") if isinstance(gid, dict) else gid
        print(f"{i['id']:<10}{gmap.get(gid, gid or '-'):<12}"
              f"{str(fmt_label(field_value(i, 'status-1'))):<14}"
              f"{fmt_person(field_value(i, 'person-1')):<24}"
              f"{str(field_value(i, 'date_time-1') or '-'):<12}{i.get('title', '')[:70]}")


def parse_kv(pairs):
    out = {}
    for p in pairs or []:
        if "=" not in p:
            raise PlakyError(f"Campo inválido (use CHAVE=valor): {p}")
        k, v = p.split("=", 1)
        try:
            v = json.loads(v)
        except (json.JSONDecodeError, ValueError):
            pass
        out[k] = v
    return out


def build_parser():
    p = argparse.ArgumentParser(description="CLI do Plaky (API pública v1)")
    p.add_argument("--json", action="store_true", help="saída JSON bruta")
    p.add_argument("--dry-run", action="store_true", help="mostra requests de escrita sem enviar")
    p.add_argument("--space", type=int, default=DEFAULT_SPACE, help="spaceId (padrão: Main space)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("me", help="usuário atual (valida a key)")
    sub.add_parser("spaces", help="lista spaces")
    b = sub.add_parser("boards", help="lista boards de um space")
    b.add_argument("--space", type=int, default=None)

    g = sub.add_parser("groups", help="lista grupos de um board")
    g.add_argument("--board", required=True)

    d = sub.add_parser("describe", help="detalhe do board (grupos + campos)")
    d.add_argument("--board", required=True)

    it = sub.add_parser("items", help="lista itens do board")
    it.add_argument("--board", required=True)
    it.add_argument("--group", default=None, help="id ou título do grupo")
    it.add_argument("--status", default=None, help="filtra por rótulo de status exato")
    it.add_argument("--assignee", default=None, help="filtra por email do responsável")
    it.add_argument("--page-size", type=int, default=50)
    it.add_argument("--max-pages", type=int, default=5)
    it.add_argument("--all", action="store_true", help="todas as páginas (até 20)")

    s = sub.add_parser("search", help="busca itens por trecho do título")
    s.add_argument("--board", required=True)
    s.add_argument("--query", required=True)
    s.add_argument("--max-pages", type=int, default=5)

    v = sub.add_parser("item", help="detalhe de um item")
    v.add_argument("item_id", type=int)
    v.add_argument("--board", required=True)

    c = sub.add_parser("create", help="cria item (ou subitem com --subitem-of)")
    c.add_argument("--board", required=True)
    c.add_argument("--title", default=None)
    c.add_argument("--group", default=None, help="id ou título do grupo")
    c.add_argument("--assignee", action="append", default=[], help="email (repetir p/ vários)")
    c.add_argument("--due", default=None, help="prazo YYYY-MM-DD ou ISO")
    c.add_argument("--status", default=None, help="rótulo inicial de status")
    c.add_argument("--subitem-of", type=int, default=None)
    c.add_argument("--field", action="append", default=[], help="CHAVE=valor (repetir)")

    f = sub.add_parser("set-field", help="altera um campo do item")
    f.add_argument("item_id", type=int)
    f.add_argument("field", help="key ou título do campo (ex.: Status)")
    f.add_argument("value", help="novo valor (label p/ status, ISO p/ data, JSON p/ demais)")
    f.add_argument("--board", required=True)

    m = sub.add_parser("move", help="move item para outro grupo")
    m.add_argument("item_id", type=int)
    m.add_argument("--group", required=True, help="id ou título do grupo destino")
    m.add_argument("--board", required=True)

    k = sub.add_parser("comment", help="comenta num item")
    k.add_argument("item_id", type=int)
    k.add_argument("--text", required=True)
    k.add_argument("--board", required=True)

    x = sub.add_parser("delete", help="apaga um item (pede confirmação)")
    x.add_argument("item_id", type=int)
    x.add_argument("--board", required=True)
    x.add_argument("--yes", action="store_true")

    u = sub.add_parser("upload", help="anexa arquivo a um item")
    u.add_argument("item_id", type=int)
    u.add_argument("--file", required=True)
    u.add_argument("--board", required=True)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    client = PlakyClient(dry_run=args.dry_run)
    space = args.space if args.space is not None else DEFAULT_SPACE
    as_json = args.json

    def out(obj):
        print(json.dumps(obj, ensure_ascii=False, indent=2) if as_json else obj)

    if args.cmd == "me":
        return out(client.me())
    if args.cmd == "spaces":
        data = client.spaces()
        if as_json:
            return out(data)
        return [print(f"{s['id']} | {s['title']} | {s.get('kind')}") for s in data]
    if args.cmd == "boards":
        data = client.boards(space)
        if as_json:
            return out(data)
        return [print(f"{b['id']} | {b['title']} | {b.get('kind')}") for b in data]
    if args.cmd == "groups":
        board = resolve_board(args.board)
        data = client.groups(space, board)
        if as_json:
            return out(data)
        return [print(f"{g['id']} | {g['title']}") for g in data]
    if args.cmd == "describe":
        board = resolve_board(args.board)
        b = client.board_details(space, board)
        if as_json:
            return out(b)
        print(f"Board {b['id']} | {b['title']}")
        print("Grupos: " + ", ".join(f"{g['title']}({g['id']})" for g in b.get("groups", [])))
        print("Campos: " + ", ".join(
            f"{f.get('key')}/{f.get('title') or '?'}:{f.get('type')}" for f in b.get("fields", [])))
        return
    if args.cmd in ("items", "search"):
        board = resolve_board(args.board)
        groups = client.groups(space, board)
        items = client.items(space, board, max_pages=args.max_pages if args.cmd == "search" else
                             (20 if getattr(args, "all", False) else 5))
        if args.cmd == "search":
            q = args.query.lower()
            items = [i for i in items if q in (i.get("title") or "").lower()]
        if getattr(args, "status", None):
            items = [i for i in items if str(fmt_label(field_value(i, "status-1"))) == args.status]
        _assignee = getattr(args, "assignee", None)
        if _assignee:
            items = [i for i in items
                     if _assignee.lower() in fmt_person(field_value(i, "person-1")).lower()
                     or any(_assignee.lower() in (u.get("email", "").lower())
                            for u in ((field_value(i, "person-1") or {}).get("assignedUsers", [])
                                      if isinstance(field_value(i, "person-1"), dict) else []))]
        if as_json:
            return out(items)
        print(f"{len(items)} item(ns) — board {board}")
        return print_items(items, groups)
    if args.cmd == "item":
        board = resolve_board(args.board)
        return out(client.item(space, board, args.item_id))
    if args.cmd == "create":
        board = resolve_board(args.board)
        gid = resolve_group(client, space, board, args.group)
        res = client.create_item(space, board, title=args.title, group=gid,
                                 assignee_emails=args.assignee, due=args.due,
                                 status=args.status, fields=parse_kv(args.field),
                                 subitem_of=args.subitem_of)
        if as_json or client.dry_run:
            return out(res)
        print(f"Criado item {res.get('id')} — {res.get('title')}")
        return
    if args.cmd == "set-field":
        board = resolve_board(args.board)
        field = resolve_field(client, space, board, args.field)
        try:
            value = json.loads(args.value)
        except (json.JSONDecodeError, ValueError):
            value = args.value
        if field == "date_time-1" and isinstance(value, str):
            value = normalize_date(value)
        res = client.set_field(space, board, args.item_id, field, value)
        if as_json or client.dry_run:
            return out(res)
        print(f"Item {args.item_id}: {field} = {args.value}")
        return
    if args.cmd == "move":
        board = resolve_board(args.board)
        gid = resolve_group(client, space, board, args.group)
        res = client.move_item(space, board, args.item_id, gid)
        if as_json or client.dry_run:
            return out(res)
        print(f"Item {args.item_id} movido para grupo {gid}")
        return
    if args.cmd == "comment":
        board = resolve_board(args.board)
        res = client.comment(space, board, args.item_id, args.text)
        if as_json or client.dry_run:
            return out(res)
        print(f"Comentário criado: id {res.get('id')}")
        return
    if args.cmd == "delete":
        board = resolve_board(args.board)
        if not args.yes and not client.dry_run:
            ans = input(f"Apagar item {args.item_id} do board {board}? [s/N] ").strip().lower()
            if ans not in ("s", "sim", "y", "yes"):
                print("Cancelado.")
                return
        res = client.delete_item(space, board, args.item_id)
        if as_json or client.dry_run:
            return out(res)
        print(f"Item {args.item_id} apagado.")
        return
    if args.cmd == "upload":
        board = resolve_board(args.board)
        res = client.upload(space, board, args.item_id, args.file)
        if as_json or client.dry_run:
            return out(res)
        print(f"Arquivo anexado: id {res.get('id')} ({res.get('name')})")
        return


if __name__ == "__main__":
    try:
        main()
    except PlakyError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        pass
