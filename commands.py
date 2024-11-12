# commands.py
from telegram import Update
from telegram.ext import ContextTypes
import requests
from datetime import datetime, timedelta
import re
import pytz
import json
import requests
from typing import Dict, Tuple

POOLS_CONFIG = {
    "stKAIA : (stKAIA-KAIA LP)": {
        "points_per_dollar": 4.32,
        "tokens": ["stKAIA"]
    },
    "KAIA : (stKAIA-KAIA LP)": {
        "points_per_dollar": 4.8,
        "tokens": ["KAIA"]
    },
    "stKAIA (LST)": {
        "points_per_dollar": 2.16,
        "tokens": ["stKAIA"]
    },
    "USDT/USDC": {
        "points_per_dollar": 3.984,
        "tokens": ["USDT"]
    },
    "USDT (WETH-USDT 20%)": {
        "points_per_dollar": 15.936,
        "tokens": ["WETH", "USDT"]
    },
    "ETH (WETH-USDT 20%)": {
        "points_per_dollar": 9.6,
        "tokens": ["WETH", "USDT"]
    },
    "KRWO (KRWO-USDT LP)": {
        "points_per_dollar": 3.984,
        "tokens": ["KRWO", "USDT"]
    }
}

def format_number(value):
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:,.2f}B"
    elif value >= 1_000_000:
        return f"{value/1_000_000:,.2f}M"
    elif value >= 1_000:
        return f"{value/1_000:,.2f}K"
    else:
        return f"{value:,.2f}"

def get_kaia_price() -> float:
    """KAIA 토큰의 현재 가격을 가져옴"""
    try:
        url = "https://api.swapscanner.io/v1/tokens/prices"
        response = requests.get(url)
        response.raise_for_status()
        kaia_address = "0x0000000000000000000000000000000000000000"
        return float(response.json().get(kaia_address, 0))
    except Exception as e:
        return f"Error fetching KAIA price: {str(e)}"
    
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
    hourly_reward = (my_points_per_hour / pool_final_points) * total_reward
    
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

def calculate_pool_returns(points_per_dollar: float, pool_data: Dict, kaia_price: float) -> Dict[str, Tuple[float, float]]:
    """
    General과 FGP 풀 각각에 대한 APY와 달러 수익을 계산
    
    Args:
        points_per_dollar: 1달러당 얻는 포인트
        pool_data: 현재 풀 데이터
        kaia_price: KAIA 토큰의 현재 가격
    
    Returns:
        Dict with 'general' and 'fgp' keys, each containing (apy_percentage, dollar_return)
    """
    remaining_hours, _ = get_remaining_time()
    if remaining_hours <= 0:
        return {'general': (0, 0), 'fgp': (0, 0)}
    
    results = {}
    hours_in_year = 8760
    
    # General Pool 계산 
    total_points_general = pool_data['generalPoint'] + (pool_data['generalPointPerHour'] * remaining_hours)
    my_points_general = points_per_dollar * remaining_hours
    kaia_reward_general = (my_points_general / total_points_general) * 10_000_000
    dollar_return_general = kaia_reward_general * kaia_price # 남은 시간 동안 예상 이율
    apy_general = (dollar_return_general * (hours_in_year / remaining_hours)) * 100
    
    # FGP Pool 계산
    total_points_fgp = pool_data['fgpPoint'] + (pool_data['fgpPointPerHour'] * remaining_hours)
    my_points_fgp = points_per_dollar * remaining_hours
    kaia_reward_fgp = (my_points_fgp / total_points_fgp) * 15_000_000
    dollar_return_fgp = kaia_reward_fgp * kaia_price
    apy_fgp = ((dollar_return_fgp) * (hours_in_year / remaining_hours)) * 100
    
    return {
        'general': (apy_general, dollar_return_general),
        'fgp': (apy_fgp, dollar_return_fgp)
    }

async def apy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 현재 풀 데이터 가져오기
        pool_data = get_kaia_pool_info()
        if isinstance(pool_data, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=pool_data,
                parse_mode='Markdown'
            )
            return
            
        # KAIA 가격 가져오기
        kaia_price = get_kaia_price()
        if kaia_price == 0:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Unable to fetch KAIA price",
                parse_mode='Markdown'
            )
            return
            
        remaining_hours, time_str = get_remaining_time()
        
        # FGP Pool 정보 (15M KAIA)
        fgp_message = "📊 *FGP POOL ROI (15M KAIA)*\n\n"
        fgp_message += f"💰 *KAIA Price*: ${kaia_price:.4f}\n"
        fgp_message += f"⌛ {time_str}\n\n"
        fgp_message += f"📈 *Current Pool Stats*\n"
        fgp_message += f"• Total Points: {format_number(pool_data['fgpPoint'])}\n"
        fgp_message += f"• Points/Hour: {format_number(pool_data['fgpPointPerHour'])}\n\n"
        fgp_message += "*Investment Returns:*\n"

        # General Pool 정보 (10M KAIA)
        general_message = "📊 *GENERAL POOL ROI (10M KAIA)*\n\n"
        general_message += f"💰 *KAIA Price*: ${kaia_price:.4f}\n"
        general_message += f"⌛ {time_str}\n\n"
        general_message += f"📈 *Current Pool Stats*\n"
        general_message += f"• Total Points: {format_number(pool_data['generalPoint'])}\n"
        general_message += f"• Points/Hour: {format_number(pool_data['generalPointPerHour'])}\n\n"
        general_message += "*Investment Returns:*\n"
        
        # 모든 풀 구성에 대해 FGP와 General 각각 계산
        for pool_name, config in POOLS_CONFIG.items():
            # $1 투자시 리턴
            returns = calculate_pool_returns(
                config['points_per_dollar'],
                pool_data,
                kaia_price
            )
            
            # $100 투자시 리턴
            returns_100 = {
                'general': (returns['general'][0], returns['general'][1] * 100),
                'fgp': (returns['fgp'][0], returns['fgp'][1] * 100)
            }
            
            # FGP Pool 메시지에 추가
            fgp_info = (
                f"\n*{pool_name}*\n"
                f"• Points per $: {config['points_per_dollar']:.3f}\n"
                f"• APY: {returns['fgp'][0]:.2f}%\n"
                f"• $100 Investment:\n"
                f"  - Return: ${returns_100['fgp'][1]:.2f}\n"
                f"  - KAIA: {(returns_100['fgp'][1]/kaia_price):.2f}\n"
            )
            fgp_message += fgp_info

            # General Pool 메시지에 추가
            general_info = (
                f"\n*{pool_name}*\n"
                f"• Points per $: {config['points_per_dollar']:.3f}\n"
                f"• APY: {returns['general'][0]:.2f}%\n"
                f"• $100 Investment:\n"
                f"  - Return: ${returns_100['general'][1]:.2f}\n"
                f"  - KAIA: {(returns_100['general'][1]/kaia_price):.2f}\n"
            )
            general_message += general_info
        
        # FGP Pool 메시지 먼저 전송
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=fgp_message,
            parse_mode='Markdown'
        )
        
        # General Pool 메시지 전송
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=general_message,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Error occurred: {str(e)}",
            parse_mode='Markdown'
        )