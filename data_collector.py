# data_collector.py
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
import os
import logging
from typing import Dict, Optional, List
from collections import defaultdict

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_collector.log'),
        logging.StreamHandler()
    ]
)

class KAIADataCollector:
    def __init__(self, 
                 data_file: str = 'kaia_pool_data.json',
                 stats_file: str = 'kaia_daily_stats.json'):
        self.api_url = "https://api-portal.kaia.io/api/v1/mission/total"
        self.data_file = data_file
        self.stats_file = stats_file
        self.last_data: Optional[Dict] = None
        self._initialize_data_file()
        self._initialize_stats_file()
    
    def _initialize_stats_file(self) -> None:
        """통계 파일 초기화"""
        try:
            if not os.path.exists(self.stats_file):
                initial_stats = {
                    "initialized_at": datetime.now().isoformat(),
                    "daily_stats": {}
                }
                with open(self.stats_file, 'w') as f:
                    json.dump(initial_stats, f, indent=2)
                logging.info(f"Created new stats file: {self.stats_file}")
        except Exception as e:
            logging.error(f"Error initializing stats file: {e}")

    def _initialize_data_file(self) -> None:
        """데이터 파일 초기화 및 로드"""
        try:
            data_dir = os.path.dirname(self.data_file)
            if data_dir and not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            if os.path.exists(self.data_file):
                self._load_existing_data()
            else:
                self._create_empty_data_file()
                
        except Exception as e:
            logging.error(f"Error initializing data file: {e}")
            self.last_data = {}

    def _create_empty_data_file(self) -> None:
        """빈 데이터 파일 생성"""
        try:
            initial_data = {
                "initialized_at": datetime.now().isoformat(),
                "data_points": []
            }
            with open(self.data_file, 'w') as f:
                json.dump(initial_data, f, indent=2)
            self.last_data = initial_data
            logging.info(f"Created new data file: {self.data_file}")
        except Exception as e:
            logging.error(f"Error creating empty data file: {e}")
            self.last_data = {}

    def _load_existing_data(self) -> None:
        """기존 저장된 데이터 로드"""
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                # 이전 형식의 데이터를 새 형식으로 변환
                if 'data_points' not in data:
                    data = {
                        "initialized_at": data.get("initialized_at", datetime.now().isoformat()),
                        "data_points": [data['data']] if 'data' in data else []
                    }
                self.last_data = data
            logging.info("Existing data loaded successfully")
        except Exception as e:
            logging.error(f"Error loading existing data: {e}")
            self._create_empty_data_file()

    async def fetch_data(self) -> Optional[Dict]:
        """API에서 데이터 가져오기"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['data']
                    else:
                        logging.error(f"API request failed with status {response.status}")
                        return None
        except Exception as e:
            logging.error(f"Error fetching data: {e}")
            return None

    def is_data_changed(self, new_data: Dict) -> bool:
        """데이터 변경 여부 확인"""
        if not self.last_data or not self.last_data.get('data_points'):
            return True
        
        try:
            last_point = self.last_data['data_points'][-1]
            return last_point['updatedAt'] != new_data['updatedAt']
        except (KeyError, IndexError):
            return True

    def save_data(self, data: Dict) -> None:
        """데이터를 JSON 파일로 저장"""
        try:
            # 현재 데이터를 데이터 포인트 리스트에 추가
            if not self.last_data:
                self.last_data = {"initialized_at": datetime.now().isoformat(), "data_points": []}
            
            self.last_data['data_points'].append(data)
            
            # 파일 저장
            with open(self.data_file, 'w') as f:
                json.dump(self.last_data, f, indent=2)
            
            logging.info(f"Data point saved successfully")
            
            # 날짜별 통계 업데이트
            self.update_daily_statistics()
            
        except Exception as e:
            logging.error(f"Error saving data: {e}")

    def update_daily_statistics(self) -> None:
        """일일 통계 계산 및 저장"""
        try:
            # 데이터 포인트들을 날짜별로 그룹화
            daily_data = defaultdict(list)
            for point in self.last_data['data_points']:
                date = datetime.fromtimestamp(point['updatedAt']).strftime('%Y-%m-%d')
                daily_data[date].append(point)

            # 각 날짜별 통계 계산
            stats = {}
            for date, points in daily_data.items():
                if len(points) >= 2:  # 최소 2개 이상의 데이터 포인트가 있어야 변화율 계산 가능
                    # 정렬된 포인트
                    sorted_points = sorted(points, key=lambda x: x['updatedAt'])
                    first_point = sorted_points[0]
                    last_point = sorted_points[-1]
                    
                    # 시간 차이 계산 (시간 단위)
                    time_diff = (last_point['updatedAt'] - first_point['updatedAt']) / 3600
                    
                    if time_diff > 0:
                        # FGP 풀 변화율 계산
                        fgp_change = last_point['fgpPoint'] - first_point['fgpPoint']
                        fgp_rate = fgp_change / time_diff
                        
                        # General 풀 변화율 계산
                        general_change = last_point['generalPoint'] - first_point['generalPoint']
                        general_rate = general_change / time_diff
                        
                        stats[date] = {
                            "fgp_hourly_average": round(fgp_rate, 2),
                            "general_hourly_average": round(general_rate, 2),
                            "time_span_hours": round(time_diff, 2),
                            "data_points": len(points),
                            "first_update": datetime.fromtimestamp(first_point['updatedAt']).isoformat(),
                            "last_update": datetime.fromtimestamp(last_point['updatedAt']).isoformat()
                        }

            # 통계 저장
            with open(self.stats_file, 'w') as f:
                json.dump({
                    "updated_at": datetime.now().isoformat(),
                    "daily_stats": stats
                }, f, indent=2)
            
            logging.info("Daily statistics updated successfully")
            
        except Exception as e:
            logging.error(f"Error updating daily statistics: {e}")

    async def run_collector(self, interval_seconds: int = 3600) -> None:
        """주기적으로 데이터 수집 및 저장"""
        logging.info(f"Starting data collection with {interval_seconds} seconds interval")
        
        while True:
            try:
                new_data = await self.fetch_data()
                
                if new_data and self.is_data_changed(new_data):
                    self.save_data(new_data)
                    logging.info("New data collected and saved")
                else:
                    logging.info("No new data to save")
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logging.error(f"Unexpected error in collector: {e}")
                await asyncio.sleep(60)  # 에러 발생 시 1분 후 재시도