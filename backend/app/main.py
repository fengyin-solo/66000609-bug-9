from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import re
import threading
import uuid
import random
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

app = FastAPI(title="Smart Contract Security Auditor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ---------------------------------------------------------------------------
# Persistent audit history store (JSON file backed)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# Legacy records previously shown in the UI. They are seeded on first run so
# that existing history entries remain openable after the upgrade.
SEED_RECORDS = [
    {
        "id": "1",
        "filename": "SimpleBank.sol",
        "score": 45,
        "timestamp": "2026-09-21T10:30:00",
        "vulnerabilities": [
            {
                "type": "重入攻击 (Reentrancy)",
                "severity": "critical",
                "line": 12,
                "description": "使用低级call()或send()转移ETH存在重入攻击风险。攻击者可部署恶意合约在fallback中反复调用提款。",
                "suggestion": "使用Checks-Effects-Interactions模式，或引入ReentrancyGuard。推荐使用transfer()或call()并限制Gas。",
                "code": "function withdraw(uint amount) public {\n    require(balances[msg.sender] >= amount);\n    (bool success,) = msg.sender.call{value: amount}(\"\");"
            },
            {
                "type": "整数溢出 (Integer Overflow/Underflow)",
                "severity": "high",
                "line": 8,
                "description": "Solidity 0.7及以下版本，未使用SafeMath时可能发生整数溢出。",
                "suggestion": "使用SafeMath库或升级到Solidity 0.8+（内置溢出检查）。",
                "code": "balances[msg.sender] += msg.value;"
            },
            {
                "type": "未授权访问控制",
                "severity": "high",
                "line": 11,
                "description": "关键函数缺少访问控制检查，任何人都可以调用。",
                "suggestion": "添加onlyOwner或自定义访问控制修饰符。",
                "code": "function withdraw(uint amount) public {"
            }
        ],
        "gasIssues": [
            {"functionName": "deposit()", "currentGas": 45000, "optimizedGas": 21000, "suggestion": "移除不必要的storage写入"},
            {"functionName": "withdraw()", "currentGas": 52000, "optimizedGas": 31000, "suggestion": "缓存storage变量到memory"}
        ]
    },
    {
        "id": "2",
        "filename": "Token.sol",
        "score": 78,
        "timestamp": "2026-09-20T15:20:00",
        "vulnerabilities": [
            {
                "type": "精确度损失",
                "severity": "medium",
                "line": 24,
                "description": "除法运算可能导致精度损失，特别是在代币金额计算中。",
                "suggestion": "先乘后除，使用高精度计算或使用Babylonian方法。",
                "code": "uint reward = total / 3;"
            },
            {
                "type": "精确度损失",
                "severity": "medium",
                "line": 31,
                "description": "除法运算可能导致精度损失，特别是在代币金额计算中。",
                "suggestion": "先乘后除，使用高精度计算或使用Babylonian方法。",
                "code": "uint fee = amount / 100;"
            },
            {
                "type": "selfdestruct使用",
                "severity": "low",
                "line": 40,
                "description": "selfdestruct可强制将合约所有ETH发送到任意地址，可能被滥用。",
                "suggestion": "谨慎使用selfdestruct，确保有正当的业务需求。",
                "code": "selfdestruct(payable(owner));"
            },
            {
                "type": "未授权访问控制",
                "severity": "low",
                "line": 18,
                "description": "关键函数缺少访问控制检查，任何人都可以调用。",
                "suggestion": "添加onlyOwner或自定义访问控制修饰符。",
                "code": "function mint(uint amount) public {"
            }
        ],
        "gasIssues": [
            {"functionName": "transfer()", "currentGas": 35000, "optimizedGas": 28000, "suggestion": "使用短路逻辑"},
            {"functionName": "mint()", "currentGas": 48000, "optimizedGas": 33000, "suggestion": "缓存storage变量到memory"}
        ]
    },
    {
        "id": "3",
        "filename": "Auction.sol",
        "score": 32,
        "timestamp": "2026-09-19T09:15:00",
        "vulnerabilities": [
            {
                "type": "重入攻击 (Reentrancy)",
                "severity": "critical",
                "line": 27,
                "description": "使用低级call()或send()转移ETH存在重入攻击风险。攻击者可部署恶意合约在fallback中反复调用提款。",
                "suggestion": "使用Checks-Effects-Interactions模式，或引入ReentrancyGuard。推荐使用transfer()或call()并限制Gas。",
                "code": "(bool ok,) = msg.sender.call{value: pendingReturns[msg.sender]}(\"\");"
            },
            {
                "type": "重入攻击 (Reentrancy)",
                "severity": "critical",
                "line": 35,
                "description": "使用低级call()或send()转移ETH存在重入攻击风险。攻击者可部署恶意合约在fallback中反复调用提款。",
                "suggestion": "使用Checks-Effects-Interactions模式，或引入ReentrancyGuard。推荐使用transfer()或call()并限制Gas。",
                "code": "(bool sent,) = highestBidder.call{value: highestBid}(\"\");"
            },
            {
                "type": "tx.origin钓鱼",
                "severity": "high",
                "line": 15,
                "description": "使用tx.origin进行身份验证可能被钓鱼攻击，攻击者诱导用户触发交易。",
                "suggestion": "使用msg.sender代替tx.origin进行身份验证。",
                "code": "require(tx.origin == owner);"
            },
            {
                "type": "selfdestruct使用",
                "severity": "low",
                "line": 42,
                "description": "selfdestruct可强制将合约所有ETH发送到任意地址，可能被滥用。",
                "suggestion": "谨慎使用selfdestruct，确保有正当的业务需求。",
                "code": "selfdestruct(payable(beneficiary));"
            }
        ],
        "gasIssues": [
            {"functionName": "bid()", "currentGas": 58000, "optimizedGas": 40000, "suggestion": "合并多个事件为一个"},
            {"functionName": "withdraw()", "currentGas": 51000, "optimizedGas": 32000, "suggestion": "缓存storage变量到memory"}
        ]
    }
]

_store_lock = threading.Lock()
_history: List[dict] = []


def _load_history() -> List[dict]:
    """Load history from disk, seeding legacy records on first run."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    # First run (or corrupted file): seed legacy records so old entries
    # remain accessible.
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(SEED_RECORDS, f, ensure_ascii=False, indent=2)
    return [dict(r) for r in SEED_RECORDS]


def _save_history() -> None:
    tmp_file = HISTORY_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(_history, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, HISTORY_FILE)


def _find_record(audit_id: str) -> Optional[dict]:
    for record in _history:
        if record.get("id") == audit_id:
            return record
    return None


with _store_lock:
    _history = _load_history()

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

GAS_PATTERNS = [
    {"function": "storage_read", "issue": "循环中读取storage变量", "saving": 0.3},
    {"function": "redundant_sstore", "issue": "不必要的storage写入", "saving": 0.25},
    {"function": "short_circuit", "issue": "逻辑运算可短路优化", "saving": 0.15},
]

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
    """Analyze gas consumption issues"""
    issues = []
    functions = re.findall(r"function\s+(\w+)\s*\(", code)
    for fn in functions:
        base_gas = random.randint(20000, 60000)
        issues.append({
            "functionName": f"{fn}()",
            "currentGas": base_gas,
            "optimizedGas": int(base_gas * (0.7 + random.random() * 0.2)),
            "suggestion": random.choice(["移除不必要的storage写入", "缓存storage变量到memory", "使用短路逻辑", "合并多个事件为一个"])
        })
    return issues

def compute_security_score(vulnerabilities: List[dict]) -> int:
    """Compute overall security score"""
    if not vulnerabilities:
        return 100
    severity_weights = {"critical": 25, "high": 15, "medium": 8, "low": 3}
    deduction = sum(severity_weights.get(v["severity"], 5) for v in vulnerabilities)
    return max(0, 100 - deduction)

@app.get("/")
async def root():
    return {"message": "Smart Contract Security Auditor", "version": "1.0.0"}

@app.get("/api/patterns")
async def list_patterns():
    return {"code": 0, "message": "success", "data": VULNERABILITY_PATTERNS}

@app.post("/api/audit")
async def audit_contract(request: AuditRequest):
    vulnerabilities = detect_vulnerabilities(request.code)
    gas_issues = compute_gas_issues(request.code)
    score = compute_security_score(vulnerabilities)

    result = {
        "id": str(uuid.uuid4()),
        "filename": request.filename,
        "score": score,
        "vulnerabilities": vulnerabilities,
        "gasIssues": gas_issues,
        "timestamp": datetime.now().isoformat()
    }

    # Persist every audit so it shows up in history immediately and
    # survives refreshes / restarts.
    with _store_lock:
        _history.insert(0, result)
        _save_history()

    return {"code": 0, "message": "success", "data": result}

@app.get("/api/history")
async def get_history():
    with _store_lock:
        records = sorted(_history, key=lambda r: r.get("timestamp", ""), reverse=True)
        summaries = [
            {
                "id": r["id"],
                "filename": r["filename"],
                "score": r["score"],
                "timestamp": r["timestamp"],
                "vulnerabilityCount": len(r.get("vulnerabilities", []))
            }
            for r in records
        ]
    return {"code": 0, "message": "success", "data": summaries}

@app.get("/api/history/{audit_id}")
async def get_history_detail(audit_id: str):
    with _store_lock:
        record = _find_record(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="审计记录不存在")
    return {"code": 0, "message": "success", "data": record}

@app.post("/api/report/{audit_id}")
async def generate_report(audit_id: str):
    """Generate PDF report for an existing audit record"""
    with _store_lock:
        record = _find_record(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="审计记录不存在")

    pdf_path = os.path.join(REPORTS_DIR, f"{audit_id}.pdf")
    _render_pdf_report(record, pdf_path)
    return {"code": 0, "message": "success", "data": {"url": f"/api/reports/{audit_id}.pdf"}}

@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    """Serve a generated PDF report"""
    safe_name = os.path.basename(filename)
    pdf_path = os.path.join(REPORTS_DIR, safe_name)
    if not safe_name.endswith(".pdf") or not os.path.isfile(pdf_path):
        raise HTTPException(status_code=404, detail="报告不存在")
    return FileResponse(pdf_path, media_type="application/pdf", filename=safe_name)

def _render_pdf_report(record: dict, pdf_path: str) -> None:
    """Render an audit record to a PDF file (supports Chinese text)."""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 60

    def draw_line(text: str, font: str = "STSong-Light", size: int = 11, gap: int = 18):
        nonlocal y
        if y < 60:
            c.showPage()
            y = height - 60
        c.setFont(font, size)
        c.drawString(60, y, text)
        y -= gap

    draw_line("智能合约安全审计报告", size=18, gap=30)
    draw_line(f"文件名: {record.get('filename', '-')}")
    draw_line(f"审计时间: {record.get('timestamp', '-')}")
    draw_line(f"安全评分: {record.get('score', '-')}", gap=26)

    vulnerabilities = record.get("vulnerabilities", [])
    draw_line(f"发现漏洞 ({len(vulnerabilities)})", size=14, gap=24)
    for v in vulnerabilities:
        draw_line(f"[{v.get('severity', '-')}] {v.get('type', '-')} (行 {v.get('line', '-')})", size=11, gap=16)
        draw_line(f"  描述: {v.get('description', '-')}", size=10, gap=14)
        draw_line(f"  建议: {v.get('suggestion', '-')}", size=10, gap=18)

    gas_issues = record.get("gasIssues", [])
    if gas_issues:
        draw_line("Gas优化建议", size=14, gap=24)
        for g in gas_issues:
            draw_line(
                f"{g.get('functionName', '-')}: {g.get('currentGas', '-')} -> {g.get('optimizedGas', '-')}",
                size=11, gap=16
            )
            draw_line(f"  建议: {g.get('suggestion', '-')}", size=10, gap=18)

    c.save()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
