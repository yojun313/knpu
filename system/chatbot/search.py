"""작은 문서 묶음용 BM25 (한글 글자 bigram + 영문/숫자 단어). 벡터 임베딩 없이 동작한다."""

import math
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]*|\d+(?:\.\d+)?|[가-힣]+")


def tokens(text: str) -> list[str]:
    out = []
    for w in _WORD.findall((text or "").lower()):
        if re.match(r"[가-힣]", w):
            out.append(w)  # 한 단어(조사 포함) 그대로
            out.extend(
                w[i : i + 2] for i in range(len(w) - 1)
            )  # 글자 bigram: 조사·띄어쓰기에 강하다
        else:
            out.append(w)
    return out


class BM25:
    def __init__(self, docs: list[dict], fields=("title", "text"), k1=1.4, b=0.7):
        self.docs = docs
        self.k1, self.b = k1, b
        self.tf = []
        df = Counter()
        for d in docs:
            # 제목은 두 번 넣어 가중한다
            toks = tokens(
                " ".join(str(d.get(f) or "") for f in fields)
                + " "
                + str(d.get("title") or "")
            )
            c = Counter(toks)
            self.tf.append((c, len(toks)))
            df.update(c.keys())
        n = max(len(docs), 1)
        self.avg = sum(l for _, l in self.tf) / n if docs else 1
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(
        self, query: str, limit: int = 8, where=None
    ) -> list[tuple[float, dict]]:
        q = Counter(tokens(query))
        scored = []
        for (c, length), d in zip(self.tf, self.docs):
            if where and not where(d):
                continue
            s = 0.0
            for t in q:
                f = c.get(t)
                if f:
                    s += (
                        self.idf.get(t, 0)
                        * f
                        * (self.k1 + 1)
                        / (f + self.k1 * (1 - self.b + self.b * length / self.avg))
                    )
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: -x[0])
        return scored[:limit]
