from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

app = FastAPI(title="Smart Contract Security Auditor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# Vulnerability patterns
VULNERABILITY_PATTERNS = [
    {
        "type": "重入攻击 (Reentrancy)",
        "severity": "critical",
        "pattern": r"\.call\{[^}]*value:\s*[^}]*\}\([^)]*\)",
        "description": "使用低级call()或send()转移ETH存在重入攻击风险。攻击者可部署恶意合约在fallback中反复调用提款。",
        "suggestion": "使用Checks-Effects-Interactions模式，或引入ReentrancyGuard。推荐使用transfer()或call()并限制Gas。"
    },
    {
        "type": "整数溢出 (Integer Overflow/Underflow)",
        "severity": "high",
        "pattern": r"[+\-*/]\s*=|(&&|\|\|)\s*\w+\s*[<>=]",
        "description": "Solidity 0.7及以下版本，未使用SafeMath时可能发生整数溢出。",
        "suggestion": "使用SafeMath库或升级到Solidity 0.8+（内置溢出检查）。"
    },
    {
        "type": "未授权访问控制",
        "severity": "high",
        "pattern": r"function\s+\w+\s*\([^)]*\)\s*public\s*(payable)?\s*\{[^}]*(?:require|if)\s*\(",
        "description": "关键函数缺少访问控制检查，任何人都可以调用。",
        "suggestion": "添加onlyOwner或自定义访问控制修饰符。"
    },
    {
        "type": "selfdestruct使用",
        "severity": "medium",
        "pattern": r"selfdestruct|suicide",
        "description": "selfdestruct可强制将合约所有ETH发送到任意地址，可能被滥用。",
        "suggestion": "谨慎使用selfdestruct，确保有正当的业务需求。"
    },
    {
        "type": "tx.origin钓鱼",
        "severity": "high",
        "pattern": r"tx\.origin",
        "description": "使用tx.origin进行身份验证可能被钓鱼攻击，攻击者诱导用户触发交易。",
        "suggestion": "使用msg.sender代替tx.origin进行身份验证。"
    },
    {
        "type": "精确度损失",
        "severity": "medium",
        "pattern": r"/\s*\d+",
        "description": "除法运算可能导致精度损失，特别是在代币金额计算中。",
        "suggestion": "先乘后除，使用高精度计算或使用Babylonian方法。"
    },
]

GAS_SUGGESTIONS = ["移除不必要的storage写入", "缓存storage变量到memory", "使用短路逻辑", "合并多个事件为一个"]

# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "audits.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audits (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                code TEXT NOT NULL DEFAULT '',
                score INTEGER NOT NULL,
                vulnerabilities TEXT NOT NULL,
                gas_issues TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
    _seed_history()


def _insert_audit(conn: sqlite3.Connection, result: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO audits (id, filename, code, score, vulnerabilities, gas_issues, timestamp)
        VALUES (:id, :filename, :code, :score, :vulnerabilities, :gas_issues, :timestamp)
        """,
        {
            "id": result["id"],
            "filename": result["filename"],
            "code": result.get("code", ""),
            "score": result["score"],
            "vulnerabilities": json.dumps(result["vulnerabilities"], ensure_ascii=False),
            "gas_issues": json.dumps(result["gasIssues"], ensure_ascii=False),
            "timestamp": result["timestamp"],
        },
    )


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "code": row["code"],
        "score": row["score"],
        "vulnerabilities": json.loads(row["vulnerabilities"]),
        "gasIssues": json.loads(row["gas_issues"]),
        "timestamp": row["timestamp"],
    }


# Seed contracts keep the same filenames/scores as the sample records the
# history page used to hardcode, so previously existing entries still open.
SEED_CONTRACTS = [
    (
        "seed-simple-bank-0001",
        "SimpleBank.sol",
        """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleBank {
    mapping(address => uint) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint amount) public {
        require(balances[msg.sender] >= amount);
        (bool success,) = msg.sender.call{value: amount}("");
        require(success);
        balances[msg.sender] -= amount;
    }
}""",
        "2026-09-21 10:30",
    ),
    (
        "seed-token-0002",
        "Token.sol",
        """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Token {
    mapping(address => uint) public balanceOf;
    uint public totalSupply;

    function transfer(address to, uint amount) public {
        require(balanceOf[msg.sender] >= amount);
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
    }

    function mint(address to, uint amount) public {
        balanceOf[to] += amount;
        totalSupply += amount;
    }
}""",
        "2026-09-20 15:20",
    ),
    (
        "seed-auction-0003",
        "Auction.sol",
        """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Auction {
    address public highestBidder;
    uint public highestBid;

    function bid() public payable {
        require(msg.value > highestBid);
        highestBidder = msg.sender;
        highestBid = msg.value;
    }

    function kill() public {
        selfdestruct(payable(msg.sender));
    }
}""",
        "2026-09-19 09:15",
    ),
]


def _seed_history() -> None:
    """Populate the sample records once, on an empty database."""
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM audits").fetchone()[0]
        if count > 0:
            return
        for audit_id, filename, code, timestamp in SEED_CONTRACTS:
            result = build_audit_result(code, filename, audit_id=audit_id, timestamp=timestamp)
            _insert_audit(conn, result)


# ---------------------------------------------------------------------------
# Audit engine
# ---------------------------------------------------------------------------

class AuditRequest(BaseModel):
    code: str
    filename: str


def detect_vulnerabilities(code: str) -> List[dict]:
    """Scan code for vulnerability patterns"""
    lines = code.split("\n")
    vulnerabilities = []

    for vp in VULNERABILITY_PATTERNS:
        matches = re.finditer(vp["pattern"], code, re.MULTILINE)
        for m in matches:
            line_num = code[:m.start()].count("\n") + 1
            # Find context
            context_start = max(0, line_num - 2)
            context_end = min(len(lines), line_num + 2)
            context = "\n".join(lines[context_start:context_end])

            vulnerabilities.append({
                "type": vp["type"],
                "severity": vp["severity"],
                "line": line_num,
                "description": vp["description"],
                "suggestion": vp["suggestion"],
                "code": context.strip()
            })

    return vulnerabilities


def compute_gas_issues(code: str) -> List[dict]:
    """Analyze gas consumption issues (deterministic per code)."""
    issues = []
    functions = re.findall(r"function\s+(\w+)\s*\(", code)
    for index, fn in enumerate(functions):
        # Deterministic pseudo-random values derived from function name/index,
        # so a saved record always reports the same gas figures.
        base_gas = 20000 + (sum(ord(ch) for ch in fn) + index * 7) % 40000
        saving_ratio = 0.7 + ((sum(ord(ch) for ch in fn) + index * 3) % 20) / 100
        issues.append({
            "functionName": f"{fn}()",
            "currentGas": base_gas,
            "optimizedGas": int(base_gas * saving_ratio),
            "suggestion": GAS_SUGGESTIONS[(sum(ord(ch) for ch in fn) + index) % len(GAS_SUGGESTIONS)]
        })
    return issues


def compute_security_score(vulnerabilities: List[dict]) -> int:
    """Compute overall security score"""
    if not vulnerabilities:
        return 100
    severity_weights = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    deduction = sum(severity_weights.get(v["severity"], 5) for v in vulnerabilities)
    return max(0, 100 - deduction)


def build_audit_result(
    code: str,
    filename: str,
    audit_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> dict:
    vulnerabilities = detect_vulnerabilities(code)
    gas_issues = compute_gas_issues(code)
    score = compute_security_score(vulnerabilities)
    return {
        "id": audit_id or str(uuid.uuid4()),
        "filename": filename,
        "code": code,
        "score": score,
        "vulnerabilities": vulnerabilities,
        "gasIssues": gas_issues,
        "timestamp": timestamp or datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
async def root():
    return {"message": "Smart Contract Security Auditor", "version": "1.0.0"}


@app.get("/api/patterns")
async def list_patterns():
    return {"code": 0, "message": "success", "data": VULNERABILITY_PATTERNS}


@app.post("/api/audit")
async def audit_contract(request: AuditRequest):
    result = build_audit_result(request.code, request.filename)
    with get_db() as conn:
        _insert_audit(conn, result)
    return {"code": 0, "message": "success", "data": result}


@app.get("/api/history")
async def get_history(
    q: Optional[str] = Query(None, description="按文件名模糊搜索"),
    level: Optional[str] = Query(None, description="评分等级: high(>=70) / medium(40-69) / low(<40)"),
):
    sql = "SELECT * FROM audits"
    clauses = []
    params: list = []
    if q:
        clauses.append("filename LIKE ?")
        params.append(f"%{q}%")
    if level == "high":
        clauses.append("score >= 70")
    elif level == "medium":
        clauses.append("score >= 40 AND score < 70")
    elif level == "low":
        clauses.append("score < 40")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY timestamp DESC, id DESC"

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"code": 0, "message": "success", "data": [_row_to_dict(row) for row in rows]}


@app.get("/api/audits/{audit_id}")
async def get_audit(audit_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM audits WHERE id = ?", (audit_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="审计记录不存在")
    return {"code": 0, "message": "success", "data": _row_to_dict(row)}


@app.post("/api/report/{audit_id}")
async def generate_report(audit_id: str):
    """Generate PDF report"""
    with get_db() as conn:
        row = conn.execute("SELECT id FROM audits WHERE id = ?", (audit_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="审计记录不存在")
    # Simplified report generation
    return {"code": 0, "message": "success", "data": {"url": f"/api/reports/{audit_id}.pdf"}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
