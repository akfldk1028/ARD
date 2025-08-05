"""
ipynb와 정확히 동일한 방식으로 샘플 데이터 다운로드
"""
import os
import urllib.request
import ssl

def download_ipynb_sample_data():
    """ipynb의 Google Colab 환경을 로컬에서 시뮬레이션"""
    
    # ipynb 코드 그대로
    google_colab_env = False  # 로컬 환경이지만 다운로드는 받자
    
    # SSL 설정 (ipynb에서와 같이)
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # 데이터 저장 경로
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    vrsfile = os.path.join(data_dir, 'sample.vrs')
    
    if not os.path.exists(vrsfile):
        print("Running ipynb pattern: downloading sample data")
        print("Installing projectaria-tools and getting sample data")
        
        # ipynb에서와 동일한 URL
        url = "https://github.com/facebookresearch/projectaria_tools/raw/main/data/mps_sample/sample.vrs"
        
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, vrsfile)
        print(f"Downloaded to: {vrsfile}")
    else:
        print(f"Sample data already exists: {vrsfile}")
    
    return vrsfile

if __name__ == "__main__":
    vrsfile = download_ipynb_sample_data()
    print(f"VRS file ready: {vrsfile}")