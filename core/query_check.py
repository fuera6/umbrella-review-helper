"""1단계: PubMed 검색식 형식 검사 (괄호·따옴표·연산자·필드 태그). 의미는 검사하지 않는다."""
import re

TAGS = {
    "tiab", "ti", "ab", "tw", "mh", "mesh", "majr", "mh:noexp", "mesh:noexp", "majr:noexp", "sh", "pt", "la", "dp",
    "pdat", "edat", "crdt", "au", "1au", "lastau", "fau", "ta", "jour", "ad", "affl", "all", "all fields", "nm", "ot",
    "sb", "filter", "pmid", "uid", "doi", "aid", "gr", "ip", "vi", "pg", "ps", "so", "is", "lid", "mhda", "jid", "rn",
    "si", "subh", "text word", "title", "title/abstract", "mesh terms", "publication type", "language", "journal",
    "author", "date - publication", "tiab:~0", "tiab:~1", "tiab:~2", "tiab:~3",
}
OPS = {"AND", "OR", "NOT"}


def check_query(q: str) -> list[str]:
    """고칠 점 목록을 돌려준다. 빈 목록이면 형식이 올바르다."""
    s = (q or "").strip()
    if not s:
        return ["검색식이 비어 있습니다."]
    errs = []
    if s.count('"') % 2:
        errs.append('큰따옴표(")가 짝이 맞지 않습니다.')
    bare = re.sub(r'"[^"]*"', '""', s)
    depth, neg = 0, False
    for ch in bare:
        depth += (ch == "(") - (ch == ")")
        neg |= depth < 0
    if neg:
        errs.append("닫는 괄호 ')'가 여는 괄호보다 먼저 나온 곳이 있습니다.")
    elif depth > 0:
        errs.append(f"여는 괄호 '('가 {depth}개 더 많습니다.")
    elif depth < 0:
        errs.append(f"닫는 괄호 ')'가 {-depth}개 더 많습니다.")
    if re.search(r"\(\s*\)", bare):
        errs.append("빈 괄호 ()가 있습니다.")
    if bare.count("[") != bare.count("]"):
        errs.append("필드 태그의 대괄호 [ ]가 짝이 맞지 않습니다.")
    for tag in re.findall(r"\[([^\]]*)\]", bare):
        if tag.strip().lower() not in TAGS:
            errs.append(f"알 수 없는 필드 태그 [{tag}] — 예: [tiab], [mh], [pt], [la], [dp]")
    low = re.findall(r"(?:^|[\s()])(and|or|not)(?=[\s()]|$)", bare)
    if low:
        errs.append(f"연산자는 대문자로 써야 합니다: {', '.join(sorted(set(low)))} → AND / OR / NOT")
    tok = bare.replace("(", " ( ").replace(")", " ) ").split()
    for i, t in enumerate(tok):
        if t not in OPS:
            continue
        a = tok[i - 1] if i > 0 else None
        b = tok[i + 1] if i + 1 < len(tok) else None
        if a is None or a == "(" or a in OPS:
            errs.append(f"'{t}' 앞에 검색어가 없습니다.")
        if b is None or b == ")":
            errs.append(f"'{t}' 뒤에 검색어가 없습니다.")
    for w in re.findall(r'(?:^|[\s("])([A-Za-z]{1,3})\*', bare):
        errs.append(f"'{w}*'처럼 * 앞 글자가 4자 미만이면 PubMed가 무시합니다.")
    return list(dict.fromkeys(errs))
