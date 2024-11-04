# commands.py
from telegram import Update
from telegram.ext import ContextTypes
import requests
from datetime import datetime, timedelta
import re
import pytz
import json

def format_number(value):
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:,.2f}B"
    elif value >= 1_000_000:
        return f"{value/1_000_000:,.2f}M"
    elif value >= 1_000:
        return f"{value/1_000:,.2f}K"
    else:
        return f"{value:,.2f}"

def get_kaia_pool_info():
    url = "https://api-portal.kaia.io/api/v1/mission/total"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()['data']
    except requests.RequestException as e:
        return f"데이터를 가져오는 데 실패했습니다: {str(e)}"

def get_remaining_time():
    """현재 시각부터 12월 25일 15시까지 남은 시간 계산 (시간 단위)"""
    seoul_tz = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_tz)
    end_time = seoul_tz.localize(datetime(2024, 12, 25, 15, 0, 0))
    
    # 시간 차이 계산
    time_diff = end_time - now
    
    # 전체 시간을 시간 단위로 계산 (소수점 버림)
    total_hours = int(time_diff.total_seconds() / 3600)
    
    if total_hours <= 0:
        return 0, "Event has ended"
    
    # 일수와 나머지 시간 계산
    days = total_hours // 24
    remaining_hours = total_hours % 24
    
    time_str = f"**{days}**Days**:{remaining_hours}**Hours Left"
    
    return total_hours, time_str

def calculate_reward(my_points, my_points_per_hour, pool_type, total_points, points_per_hour, remaining_hours):
    """보상 계산 함수"""
    # 종료 시점의 예상 포인트 계산
    my_final_points = my_points + (my_points_per_hour * remaining_hours)
    pool_final_points = total_points + (points_per_hour * remaining_hours)
    
    # 풀 타입에 따른 총 보상량 설정
    total_reward = 10_000_000 if pool_type == "general" else 15_000_000  # KAIA 개수
    
    # 보상 계산
    reward = (my_final_points / pool_final_points) * total_reward
    hourly_reward = (my_points_per_hour / points_per_hour) * total_reward
    
    return reward, hourly_reward

async def total_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = get_kaia_pool_info()
        if isinstance(data, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=data,
                parse_mode='Markdown'
            )
            return

        _, time_str = get_remaining_time()

        message = f"""
📊 *KAIA Pool Information*

💫 *Total Points*: {format_number(data['totalPoint'])}

🏢 *General Pool*
• Hourly: {format_number(data['generalPointPerHour'])} points/hour
• Total: {format_number(data['generalPoint'])} points

🌟 *FGP Pool*
• Hourly: {format_number(data['fgpPointPerHour'])} points/hour
• Total: {format_number(data['fgpPoint'])} points

⏰ Last Updated: {datetime.fromtimestamp(data['updatedAt']).strftime('%Y-%m-%d %H:%M:%S')}
⌛ Time Left: {time_str}
"""
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )

async def tvl_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = get_kaia_pool_info()
        if isinstance(data, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=data,
                parse_mode='Markdown'
            )
            return

        message = f"""
💰 *KAIA DeFi TVL*
${format_number(data['defiTvl'])}

⏰ Last Updated: {datetime.fromtimestamp(data['updatedAt']).strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )

async def calc_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 입력 파싱
        args = context.args
        if len(args) != 2:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Usage: /calc <my_current_points> <my_points_per_hour>\nExample: /calc 500M 2M",
                parse_mode='Markdown'
            )
            return

        # 입력값 파싱 함수
        def parse_number(value):
            match = re.match(r'^(\d+\.?\d*)(B|M|K)?$', value.upper())
            if not match:
                raise ValueError(f"Invalid number format: {value}")
            num, unit = match.groups()
            num = float(num)
            if unit == 'B':
                return num * 1_000_000_000
            elif unit == 'M':
                return num * 1_000_000
            elif unit == 'K':
                return num * 1_000
            return num

        my_points = parse_number(args[0])
        my_points_per_hour = parse_number(args[1])

        # 현재 풀 정보 가져오기
        data = get_kaia_pool_info()
        if isinstance(data, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=data,
                parse_mode='Markdown'
            )
            return

        # 남은 시간 계산
        remaining_hours, time_str = get_remaining_time()
        
        if remaining_hours <= 0:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Event has already ended.",
                parse_mode='Markdown'
            )
            return

        # 일반 풀과 FGP 풀 각각의 보상 계산
        general_reward, general_hourly = calculate_reward(
            my_points, my_points_per_hour, "general",
            data['generalPoint'], data['generalPointPerHour'],
            remaining_hours
        )

        fgp_reward, fgp_hourly = calculate_reward(
            my_points, my_points_per_hour, "fgp",
            data['fgpPoint'], data['fgpPointPerHour'],
            remaining_hours
        )

        message = f"""
🧮 *KAIA Reward Calculator*

💎 *Your Input*
• Current Points: {format_number(my_points)}
• Points per Hour: {format_number(my_points_per_hour)}

🏢 *General Pool (10M KAIA)*
• Hourly Reward: {format_number(general_hourly)} KAIA/hour
• Total Expected Reward: {format_number(general_reward)} KAIA

🌟 *FGP Pool (15M KAIA)*
• Hourly Reward: {format_number(fgp_hourly)} KAIA/hour
• Total Expected Reward: {format_number(fgp_reward)} KAIA

⌛ Time Left: {time_str}
"""

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='Markdown'
        )
    except ValueError as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Input error: {str(e)}",
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )

async def average_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args or len(context.args) != 1:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Usage: /average YYYY-MM-DD\nExample: /average 2024-11-02",
                parse_mode='Markdown'
            )
            return

        date = context.args[0]
        
        # Load daily stats
        try:
            with open('kaia_daily_stats.json', 'r') as f:
                stats = json.load(f)
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="No statistics data available.",
                parse_mode='Markdown'
            )
            return

        daily_stats = stats.get('daily_stats', {}).get(date)
        if not daily_stats:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"No data available for {date}",
                parse_mode='Markdown'
            )
            return

        message = f"""
📊 *Daily Average Stats for {date}*

🏢 *General Pool*
• Average Points/Hour: {format_number(daily_stats['general_hourly_average'])}

🌟 *FGP Pool*
• Average Points/Hour: {format_number(daily_stats['fgp_hourly_average'])}

📝 *Details*
• Data Points: {daily_stats['data_points']}
• Time Span: {daily_stats['time_span_hours']:.2f} hours
• First Update: {daily_stats['first_update']}
• Last Update: {daily_stats['last_update']}
"""
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='Markdown'
        )

    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )
async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = get_kaia_pool_info()
        if isinstance(data, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=data,
                parse_mode='Markdown'
            )
            return

        # 오늘 날짜의 통계 데이터 로드
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            with open('kaia_daily_stats.json', 'r') as f:
                stats = json.load(f)
                daily_stats = stats.get('daily_stats', {}).get(today)
                if not daily_stats:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"No statistics available for today ({today})",
                        parse_mode='Markdown'
                    )
                    return
        except FileNotFoundError:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Statistics file not found",
                parse_mode='Markdown'
            )
            return

        remaining_hours, time_str = get_remaining_time()
        
        # 오늘의 평균 시간당 포인트 사용
        general_hourly = daily_stats['general_hourly_average']
        fgp_hourly = daily_stats['fgp_hourly_average']
        
        # 시간당 보상 비율 계산
        general_hourly_reward_ratio = 10_000_000 / general_hourly
        fgp_hourly_reward_ratio = 15_000_000 / fgp_hourly
        hourly_ratio = general_hourly_reward_ratio / fgp_hourly_reward_ratio
        
        # 총 예상 포인트 계산
        general_total = data['generalPoint'] + (general_hourly * remaining_hours)
        fgp_total = data['fgpPoint'] + (fgp_hourly * remaining_hours)
        
        # 총 보상 비율 계산
        general_total_reward_ratio = 10_000_000 / general_total
        fgp_total_reward_ratio = 15_000_000 / fgp_total
        total_ratio = general_total_reward_ratio / fgp_total_reward_ratio

        message = f"""
⚖️ *Pool Efficiency Comparison*

📊 *Current Points*
• General Pool: {format_number(data['generalPoint'])} points (10M KAIA)
• FGP Pool: {format_number(data['fgpPoint'])} points (15M KAIA)

⏱️ *Today's Average Hourly Points and Rewards*
• General: {format_number(general_hourly)} points/hour
• FGP: {format_number(fgp_hourly)} points/hour
• Ratio (General : FGP) = 1 : {hourly_ratio:.3f}
• {'🔴 General Pool More Efficient' if hourly_ratio > 1 else '🟢 FGP Pool More Efficient'}

📈 *Expected Total Points and Rewards*
• General: {format_number(general_total)} points 
• FGP: {format_number(fgp_total)} points
• Ratio (General : FGP) = 1 : {total_ratio:.3f}
• {'🔴 General Pool More Efficient' if total_ratio > 1 else '🟢 FGP Pool More Efficient'}

📆 Stats from: {today}
⏰ Data Points: {daily_stats['data_points']}
⌛ Time Left: {time_str}

Note: Lower ratio indicates better efficiency
"""
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            parse_mode='Markdown'
        )
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )