/**
 * ChatGPT Owner 降级控制台 - 前端逻辑
 */

// API 配置
const API_BASE = '/api';

// 状态
let selectedRole = 'standard-user';
let isProcessing = false;
let stats = { total: 0, success: 0, failed: 0 };

// DOM 元素
const tokenInput = document.getElementById('tokenInput');
const startBtn = document.getElementById('startBtn');
const resultList = document.getElementById('resultList');
const processingIndicator = document.getElementById('processingIndicator');
const totalCount = document.getElementById('totalCount');
const successCount = document.getElementById('successCount');
const failedCount = document.getElementById('failedCount');

// 初始化角色切换按钮
document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        if (isProcessing) return;
        document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedRole = btn.dataset.role;
    });
});

/**
 * 解析输入的 Token
 * 支持: 纯 Token, JSON Session, 多行 Token
 */
function parseTokens(input) {
    const tokens = [];
    const lines = input.trim().split('\n').filter(line => line.trim());

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        // 尝试解析为 JSON
        if (trimmed.startsWith('{')) {
            try {
                const json = JSON.parse(trimmed);
                if (json.accessToken) {
                    tokens.push({
                        raw: trimmed,
                        accessToken: json.accessToken,
                        accountId: json.account?.id,
                        email: json.user?.email
                    });
                    continue;
                }
            } catch (e) {
                // 不是有效的 JSON，当作普通 token 处理
            }
        }

        // 纯 Token (JWT 格式)
        if (trimmed.includes('.') && trimmed.length > 100) {
            tokens.push({
                raw: trimmed,
                accessToken: trimmed,
                accountId: null,
                email: null
            });
        }
    }

    return tokens;
}

/**
 * 开始处理
 */
async function startProcess() {
    const input = tokenInput.value.trim();
    if (!input) {
        showNotification('请输入 Token', 'error');
        return;
    }

    const tokens = parseTokens(input);
    if (tokens.length === 0) {
        showNotification('未识别到有效的 Token', 'error');
        return;
    }

    isProcessing = true;
    startBtn.disabled = true;
    processingIndicator.style.display = 'flex';

    // 清空结果列表
    resultList.innerHTML = '';

    // 重置统计
    stats = { total: tokens.length, success: 0, failed: 0 };
    updateStats();

    // 逐个处理
    for (let i = 0; i < tokens.length; i++) {
        const token = tokens[i];
        const result = await demoteOwner(token);
        displayResult(result, i + 1);

        // 添加延迟，避免请求过快
        if (i < tokens.length - 1) {
            await sleep(500);
        }
    }

    isProcessing = false;
    startBtn.disabled = false;
    processingIndicator.style.display = 'none';

    showNotification(`处理完成: ${stats.success} 成功, ${stats.failed} 失败`,
        stats.failed === 0 ? 'success' : 'warning');
}

/**
 * 调用降级 API
 */
async function demoteOwner(token) {
    try {
        const response = await fetch(`${API_BASE}/demote/owner`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                access_token: token.raw,
                account_id: token.accountId,
                role: selectedRole
            })
        });

        const data = await response.json();

        if (data.success) {
            stats.success++;
        } else {
            stats.failed++;
        }
        updateStats();

        return {
            success: data.success,
            email: data.email || token.email || '未知邮箱',
            message: data.message,
            error: data.error,
            role: selectedRole
        };
    } catch (error) {
        stats.failed++;
        updateStats();

        return {
            success: false,
            email: token.email || '未知邮箱',
            message: '请求失败',
            error: error.message,
            role: selectedRole
        };
    }
}

/**
 * 显示处理结果
 */
function displayResult(result, index) {
    const roleText = result.role === 'standard-user' ? '普通成员' : '管理员';

    const html = `
        <div class="result-item ${result.success ? 'success' : 'failed'}">
            <div class="result-header">
                <span class="result-email">${escapeHtml(result.email)}</span>
                <span class="result-status ${result.success ? 'success' : 'failed'}">
                    ${result.success ? '✓ 成功' : '✗ 失败'}
                </span>
            </div>
            <div class="result-message">
                ${escapeHtml(result.message)}
                ${result.success ? ` → ${roleText}` : ''}
            </div>
            ${result.error ? `<div class="result-error">${escapeHtml(result.error)}</div>` : ''}
        </div>
    `;

    resultList.insertAdjacentHTML('beforeend', html);
    resultList.scrollTop = resultList.scrollHeight;
}

/**
 * 更新统计
 */
function updateStats() {
    totalCount.textContent = stats.total;
    successCount.textContent = stats.success;
    failedCount.textContent = stats.failed;
}

/**
 * 清空所有
 */
function clearAll() {
    if (isProcessing) {
        showNotification('正在处理中，请等待完成', 'warning');
        return;
    }

    tokenInput.value = '';
    resultList.innerHTML = `
        <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
                <rect x="9" y="3" width="6" height="4" rx="1"/>
                <path d="M9 12h6"/>
                <path d="M9 16h6"/>
            </svg>
            <p>暂无处理记录</p>
            <span>输入 Token 后点击开始处理</span>
        </div>
    `;
    stats = { total: 0, success: 0, failed: 0 };
    updateStats();
}

/**
 * 显示通知
 */
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 500;
        z-index: 1000;
        animation: slideIn 0.3s ease;
        ${type === 'success' ? 'background: #22c55e; color: white;' : ''}
        ${type === 'error' ? 'background: #ef4444; color: white;' : ''}
        ${type === 'warning' ? 'background: #f59e0b; color: white;' : ''}
        ${type === 'info' ? 'background: #6366f1; color: white;' : ''}
    `;
    notification.textContent = message;

    document.body.appendChild(notification);

    // 3秒后移除
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * 工具函数
 */
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// 初始化
console.log('ChatGPT Owner 降级控制台已加载');
