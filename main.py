import requests
import json
import os
import pandas as pd
import datetime

# ============================================
# ⚙️ 配置区域
# ============================================

# 从环境变量获取 Webhook (GitHub Actions 里配置)
# 如果你在本地运行，可以直接把链接填在这里的引号里
# 优先尝试从环境变量拿（GitHub专用），拿不到就用后面这个默认值（本地专用）
WEBHOOK_URL = os.environ.get("WECOM_WEBHOOK", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=b0ae8dc6-1177-4126-b676-9c91d248d4be")FRIEND_LIST = ["bu-huo-m", "xie-luo-feng-sui-9", "vigilant-boydhaq"]
HISTORY_FILE = "history.json"

# ============================================
# 🛠️ 核心函数
# ============================================

def get_total_solved(user_slug):
    """获取用户刷题总数 (无需 Cookie)"""
    url = "https://leetcode.cn/graphql/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Content-Type': 'application/json'
    }
    
    query = """
    query userQuestionProgress($userSlug: String!) {
      userProfileUserQuestionProgress(userSlug: $userSlug) {
        numAcceptedQuestions {
          count
        }
      }
    }
    """
    
    try:
        resp = requests.post(url, headers=headers, json={
            "operationName": "userQuestionProgress",
            "variables": {"userSlug": user_slug},
            "query": query
        }, timeout=10)
        
        data = resp.json()
        if 'data' in data and data['data']['userProfileUserQuestionProgress']:
            questions = data['data']['userProfileUserQuestionProgress']['numAcceptedQuestions']
            return sum(q['count'] for q in questions)
        return None
    except Exception as e:
        print(f"Error fetching {user_slug}: {e}")
        return None

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def send_wechat_msg(markdown_text):
    """
    专门适配企业微信机器人的发送函数
    """
    if not WEBHOOK_URL:
        print("❌ 未配置 Webhook，跳过发送")
        return

    headers = {'Content-Type': 'application/json'}
    
    # 企业微信的消息体格式
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_text
        }
    }
    
    try:
        resp = requests.post(WEBHOOK_URL, json=data, headers=headers)
        if resp.json().get('errcode') == 0:
            print("✅ 消息已推送至企业微信")
        else:
            print(f"❌ 发送失败: {resp.text}")
    except Exception as e:
        print(f"❌ 发送异常: {e}")

def main():
    # 1. 读取历史
    history = load_history()
    new_history = {}
    report_data = []
    
    print("🚀 开始获取数据...")
    
    for user in FRIEND_LIST:
        current_total = get_total_solved(user)
        
        if current_total is not None:
            last_total = history.get(user, current_total)
            delta = current_total - last_total
            
            report_data.append({
                "User": user,
                "Total": current_total,
                "Delta": delta
            })
            
            new_history[user] = current_total
            print(f"   - {user}: {current_total} (新增 {delta})")
        else:
            # 获取失败时不更新历史，保留旧值
            new_history[user] = history.get(user, 0)
            print(f"   - {user}: 获取失败")

    # 2. 保存快照 (供 GitHub Actions 提交)
    save_history(new_history)
    
    # 3. 生成并发送战报
    if report_data:
        df = pd.DataFrame(report_data)
        # 按新增题目降序，如果新增一样，按总数降序
        df = df.sort_values(by=["Delta", "Total"], ascending=False)
        
        # --- 构造 Markdown (企业微信版) ---
        # 企业微信支持绿色字体 <font color="info">Text</font>
        # 橙色/红色字体 <font color="warning">Text</font>
        
        now_str = datetime.datetime.now().strftime('%m-%d %H:%M')
        
        md_text = f"# 🏆 算法小分队战报\n"
        md_text += f"📅 统计时间：{now_str}\n"
        md_text += f"> 今日全员累计新增：**{sum(df['Delta'])}** 题\n\n"
        
        rank = 1
        for _, row in df.iterrows():
            # 格式化表现
            if row['Delta'] > 0:
                delta_str = f"<font color=\"warning\">+{row['Delta']}</font>"
                icon = "🔥"
            else:
                delta_str = "+0"
                icon = "😴"
                
            # 企业微信 Markdown 表格支持不是特别完美，建议用列表或简易拼贴
            # 这里使用引言格式，手机端阅读体验更好
            md_text += f"**No.{rank} {row['User']}** {icon}\n"
            md_text += f"└ 总刷题：`{row['Total']}`  今日：{delta_str}\n\n"
            rank += 1
            
        md_text += "--------\n"
        md_text += "💪 *每天进步一点点，坚持就是胜利！*"
        
        send_wechat_msg(md_text)

if __name__ == "__main__":
    main()
