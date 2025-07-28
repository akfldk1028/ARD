# //D:\Data\05_CGXR\250728_ARD\ARD\mps\management\commands\download_sample_data.py

import os
from tqdm import tqdm
from urllib.request import urlretrieve
from zipfile import ZipFile
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'MPS 튜토리얼 샘플 데이터 다운로드'

    def handle(self, *args, **options):
        mps_sample_path = getattr(settings, 'MPS_SAMPLE_DATA_PATH', '/tmp/mps_sample_data/')
        base_url = "https://www.projectaria.com/async/sample/download/?bucket=mps&filename="
        os.makedirs(mps_sample_path, exist_ok=True)

        # 튜토리얼과 동일한 파일들
        filenames = [
            "sample.vrs",
            "slam_v1_1_0.zip",
            "eye_gaze_v3_1_0.zip",
            "hand_tracking_v2_0_0.zip"
        ]

        self.stdout.write("샘플 데이터 다운로드 시작...")
        for filename in filenames:
            self.stdout.write(f"Processing: {filename}")
            full_path = os.path.join(mps_sample_path, filename)

            if os.path.isfile(full_path):
                self.stdout.write(f"{full_path} 이미 존재")
                continue

            self.stdout.write(f"다운로드: {filename}")
            urlretrieve(f"{base_url}{filename}", full_path)

            if filename.endswith(".zip"):
                with ZipFile(full_path, 'r') as zip_ref:
                    zip_ref.extractall(path=mps_sample_path)

        self.stdout.write(self.style.SUCCESS('샘플 데이터 다운로드 완료!'))