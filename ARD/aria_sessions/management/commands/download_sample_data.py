"""
ipynb 패턴을 따라 샘플 데이터 다운로드
"""
from django.core.management.base import BaseCommand
import os
import urllib.request
import ssl

class Command(BaseCommand):
    help = 'Download Project Aria sample data following ipynb pattern'

    def handle(self, *args, **options):
        # SSL 설정 (ipynb에서와 같이)
        ssl._create_default_https_context = ssl._create_unverified_context
        
        # 데이터 저장 경로
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        vrs_file = os.path.join(data_dir, 'sample.vrs')
        
        # ipynb와 동일한 URL에서 sample.vrs 다운로드
        if not os.path.exists(vrs_file):
            self.stdout.write('Downloading sample.vrs...')
            urllib.request.urlretrieve(
                "https://github.com/facebookresearch/projectaria_tools/raw/main/data/mps_sample/sample.vrs",
                vrs_file
            )
            self.stdout.write(self.style.SUCCESS(f'Downloaded: {vrs_file}'))
        else:
            self.stdout.write(f'Sample data already exists: {vrs_file}')