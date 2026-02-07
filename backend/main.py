"""
ChatGPT Business Owner 降级代理服务
用于将 ChatGPT Team/Enterprise 的 Owner 降级为 Admin 或 Member
使用 DrissionPage 绕过 Cloudflare 防护
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import base64
import json
import logging
import os
import re
import time

from DrissionPage import Chromium, ChromiumOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ChatGPT Owner 降级服务", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DemoteRequest(BaseModel):
    access_token: str
    account_id: Optional[str] = None
    role: str = "standard-user"


class DemoteResponse(BaseModel):
    success: bool
    message: str
    email: Optional[str] = None
    original_role: Optional[str] = None
    new_role: Optional[str] = None
    error: Optional[str] = None


def decode_jwt_payload(token: str) -> dict:
    """解码 JWT Token 的 payload 部分"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")
        
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        raise ValueError(f"Failed to decode JWT: {str(e)}")


def extract_user_info(token: str, session_data: dict = None) -> dict:
    """从 Token 和 Session 数据中提取用户信息
    
    优先从 session_data 获取（更准确），其次从 JWT 解析
    """
    result = {"user_id": None, "account_id": None, "email": None}
    
    # 优先从 session_data 获取 (这是最准确的)
    if session_data:
        # user.id 是正确的 user_id
        if "user" in session_data:
            result["user_id"] = session_data["user"].get("id")
            result["email"] = session_data["user"].get("email")
        # account.id 是正确的 account_id
        if "account" in session_data:
            result["account_id"] = session_data["account"].get("id")
        
        # 如果已经获取到，直接返回
        if result["user_id"] and result["account_id"]:
            logger.info(f"从 Session 提取: user_id={result['user_id']}, account_id={result['account_id']}")
            return result
    
    # 备选：从 JWT Token 解析
    try:
        payload = decode_jwt_payload(token)
        
        # 从 auth 获取
        auth_info = payload.get("https://api.openai.com/auth", {})
        
        # chatgpt_account_user_id 格式可能是: user-xxx__account-id
        account_user_id = auth_info.get("chatgpt_account_user_id", "")
        if account_user_id:
            if "__" in account_user_id:
                parts = account_user_id.split("__")
                if not result["user_id"]:
                    result["user_id"] = parts[0]
                if not result["account_id"] and len(parts) > 1:
                    result["account_id"] = parts[1]
            else:
                # 可能只有 user_id
                if not result["user_id"]:
                    result["user_id"] = account_user_id
        
        # 获取邮箱
        profile = payload.get("https://api.openai.com/profile", {})
        if not result["email"]:
            result["email"] = profile.get("email")
            
        logger.info(f"从 JWT 提取: user_id={result['user_id']}, account_id={result['account_id']}")
            
    except Exception as e:
        logger.warning(f"JWT decode error: {e}")
    
    return result


def create_browser():
    """创建带有反检测配置的浏览器实例"""
    options = ChromiumOptions()
    
    ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36'
    options.set_user_agent(ua)

    # Use a persistent local profile for CF clearance cookies.
    profile_dir = os.getenv("BROWSER_USER_DATA_DIR", os.path.abspath("./.browser-profile"))
    options.set_user_data_path(profile_dir)
    options.set_user(os.getenv("BROWSER_PROFILE", "Default"))
    
    headless = os.getenv('HEADLESS', 'false').lower() == 'true'
    if headless:
        options.set_argument('--headless=new')
    
    # Optional anti-detection tweaks. Keep off by default to avoid over-fingerprinting.
    if os.getenv('ANTI_DETECTION', 'false').lower() == 'true':
        options.set_argument('--disable-blink-features=AutomationControlled')
    options.set_argument('--no-sandbox')
    options.set_argument('--disable-dev-shm-usage')
    options.set_argument('--disable-gpu')
    options.set_argument('--lang=zh-CN')
    options.set_argument('--window-size=1920,1080')
    
    options.set_pref('credentials_enable_service', False)
    options.set_pref('profile.password_manager_enabled', False)
    
    browser = Chromium(options)
    return browser


def inject_anti_detection(page):
    """注入反检测脚本"""
    script = '''
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
    window.chrome = { runtime: {} };
    '''
    try:
        page.run_js(script)
    except Exception as e:
        logger.warning(f"注入反检测脚本失败: {e}")


def normalize_access_token(raw_value: str) -> tuple[str, Optional[dict]]:
    """Normalize token input from UI and optionally return parsed session JSON."""
    raw = raw_value.strip()
    session_data = None

    if raw.startswith('{'):
        try:
            session_data = json.loads(raw)
            token = session_data.get("accessToken", "").strip()
            if token:
                return token, session_data
            raise ValueError("accessToken not found in session data")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e

    # Handle lines like: "accessToken": "xxx..."
    match = re.search(r'"accessToken"\s*:\s*"([^"]+)"', raw)
    if match:
        return match.group(1).strip(), None

    # Strip common wrappers/trailing separators and keep JWT-looking token.
    candidate = raw.strip().strip(",").strip().strip('"').strip("'")
    if candidate.lower().startswith("accesstoken:"):
        candidate = candidate.split(":", 1)[1].strip().strip('"').strip("'")

    return candidate, None


def is_cf_block_text(text: str) -> bool:
    if not isinstance(text, str):
        return False

    t = text.lower()
    markers = (
        "enable javascript and cookies to continue",
        "cf_chl_opt",
        "cdn-cgi/challenge-platform",
        "just a moment",
    )
    return any(marker in t for marker in markers)


def extract_cf_challenge_path(text: str) -> Optional[str]:
    if not isinstance(text, str):
        return None

    # Prefer cUPMDTk/fa path from challenge config.
    patterns = [
        r'cUPMDTk:"([^"]+)"',
        r'fa:"([^"]+)"',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            path = m.group(1)
            path = path.replace('\\/', '/').replace('\\u0026', '&')
            if path.startswith('/'):
                return path
    return None


def wait_for_cf_ready(page, timeout_seconds: int = 25) -> bool:
    """Wait until page is likely out of Cloudflare challenge state."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            page.wait.doc_loaded()
            url = (page.url or "").lower()
            title = (page.title or "").lower()
            body_hint = page.run_js(
                "return document.body ? document.body.innerText.slice(0, 300) : '';"
            )

            challenged = (
                "cdn-cgi/challenge-platform" in url
                or "just a moment" in title
                or is_cf_block_text(body_hint or "")
            )
            if not challenged:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def wait_for_cf_ready_with_manual_hint(page, headless: bool) -> bool:
    auto_wait = int(os.getenv("CF_AUTO_WAIT_SECONDS", "30"))
    if wait_for_cf_ready(page, timeout_seconds=auto_wait):
        return True

    # In non-headless mode, allow manual challenge solving window.
    if not headless:
        manual_wait = int(os.getenv("CF_MANUAL_WAIT_SECONDS", "120"))
        logger.warning(f"检测到 Cloudflare challenge，请在浏览器中手动完成验证，等待 {manual_wait}s ...")
        return wait_for_cf_ready(page, timeout_seconds=manual_wait)

    return False


def execute_demote_request(access_token: str, account_id: str, user_id: str, role: str) -> dict:
    """使用浏览器执行降级请求"""
    browser = None
    try:
        logger.info("创建浏览器实例...")
        browser = create_browser()
        page = browser.latest_tab
        headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        
        # 打开 chatgpt.com
        logger.info("打开 chatgpt.com...")
        page.get('https://chatgpt.com')
        
        # 注入反检测脚本（默认关闭）
        if os.getenv('ANTI_DETECTION', 'false').lower() == 'true':
            inject_anti_detection(page)
        
        # 等待页面完全加载
        logger.info("等待页面加载...")
        page.wait.doc_loaded()
        wait_for_cf_ready_with_manual_hint(page, headless=headless)
        
        current_url = page.url
        logger.info(f"当前页面 URL: {current_url}")
        
        # 正确的 API 路径: /accounts/{account_id}/users/{user_id}
        # 注意是 users 不是 members !
        url = f"https://chatgpt.com/backend-api/accounts/{account_id}/users/{user_id}"
        logger.info(f"目标 API: {url}")
        
        # Use async function form that DrissionPage can call directly.
        js_code = '''
        async function(url, token, role) {
            try {
                const response = await fetch(url, {
                    method: "PATCH",
                    headers: {
                        "Authorization": "Bearer " + token,
                        "Content-Type": "application/json",
                        "Accept": "*/*"
                    },
                    body: JSON.stringify({ role: role })
                });

                const status = response.status;
                const text = await response.text();
                let data = null;
                try {
                    data = JSON.parse(text);
                } catch (e) {
                    data = text;
                }

                return { status: status, data: data };
            } catch (error) {
                return { error: error && error.message ? error.message : String(error) };
            }
        }
        '''
        
        for attempt in range(1, 4):
            logger.info(f"执行 fetch 请求... (attempt {attempt}/3)")
            result_data = page.run_js(js_code, url, access_token, role)
            if not result_data:
                if attempt < 3:
                    wait_for_cf_ready(page, timeout_seconds=20)
                    continue
                return {"success": False, "error": "请求超时或无响应"}
            status = result_data.get("status")
            data = result_data.get("data")

            if result_data.get("error"):
                return {"success": False, "error": result_data.get("error")}
            if status == 200:
                return {"success": True, "data": data}

            if status == 403 and is_cf_block_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)):
                logger.warning("检测到 Cloudflare challenge 拦截，等待后重试...")
                if attempt < 3:
                    challenge_text = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
                    challenge_path = extract_cf_challenge_path(challenge_text)
                    if challenge_path:
                        challenge_url = f"https://chatgpt.com{challenge_path}"
                        logger.info(f"打开 challenge 页面: {challenge_url}")
                        page.get(challenge_url)
                    else:
                        page.get(url)

                    wait_for_cf_ready_with_manual_hint(page, headless=headless)
                    page.get('https://chatgpt.com')
                    wait_for_cf_ready_with_manual_hint(page, headless=headless)
                    continue

            return {"success": False, "status": status, "data": data}

        return {"success": False, "error": "请求失败，可能被 Cloudflare 持续拦截"}
            
    except Exception as e:
        logger.error(f"浏览器执行失败: {e}")
        return {"success": False, "error": str(e)}
    finally:
        if browser:
            try:
                browser.quit()
            except:
                pass


@app.post("/api/demote/owner", response_model=DemoteResponse)
async def demote_owner(request: DemoteRequest):
    """将 Owner 降级为 Admin 或 Member
    
    重要：请提供完整的 JSON session 数据（从 chatgpt.com/api/auth/session 获取）
    这样可以准确获取 account_id 和 user_id
    """
    
    valid_roles = ["standard-user", "account-admin"]
    if request.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
    
    try:
        access_token, session_data = normalize_access_token(request.access_token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if session_data:
        logger.info("检测到完整 Session JSON")
    else:
        logger.warning("输入的是纯 Token，建议使用完整的 Session JSON 以获取准确的 user_id 和 account_id")
    
    # 提取用户信息
    user_info = extract_user_info(access_token, session_data)
    
    user_id = user_info["user_id"]
    account_id = request.account_id or user_info["account_id"]
    email = user_info["email"]
    
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Could not extract user_id. Please provide the full session JSON from chatgpt.com/api/auth/session"
        )
    if not account_id:
        raise HTTPException(
            status_code=400, 
            detail="Could not extract account_id. Please provide the full session JSON or specify account_id explicitly."
        )
    
    logger.info(f"开始降级: user={user_id}, account={account_id}, role={request.role}, email={email}")
    result = execute_demote_request(access_token, account_id, user_id, request.role)
    
    if result.get("success"):
        role_display = "普通成员" if request.role == "standard-user" else "管理员"
        return DemoteResponse(
            success=True,
            message=f"成功降级为{role_display}",
            email=email,
            new_role=request.role
        )
    else:
        error_msg = result.get("error") or f"HTTP {result.get('status')}: {result.get('data')}"
        return DemoteResponse(
            success=False,
            message="降级失败",
            email=email,
            error=error_msg
        )


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "ChatGPT Owner 降级服务 (Browser Mode)", "version": "2.1.0"}


app.mount("/static", StaticFiles(directory="../frontend"), name="static")


@app.get("/")
async def serve_frontend():
    return FileResponse("../frontend/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
