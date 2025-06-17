"""
작성자 : 노건표
작성일 : 2025-06-01 
작성내용 : 리팩토링 ( 파일 처리를 담당하는 클래스 )
calculate_file_hash : 기존의 파일과 동일한지를 비교하기 위하여 파일의 해시를 계산.
read_wbs_to_json_text : WBS 엑셀 파일을 읽어 JSON 문자열로 변환.

"""
import pandas as pd
import hashlib
import os

def calculate_file_hash(file_path: str) -> str:
    """주어진 파일의 SHA256 해시를 계산합니다."""
    hasher = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        print(f"오류: 해시 계산을 위한 파일을 찾을 수 없습니다 - {file_path}")
        raise
    except Exception as e:
        print(f"파일 해시 계산 중 오류 발생 ({file_path}): {e}")
        raise

def read_wbs_to_json_text(wbs_file_path: str) -> str:

    if not os.path.exists(wbs_file_path):
        raise FileNotFoundError(f"WBS 파일을 찾을 수 없습니다: {wbs_file_path}")
    try:
        print(f"WBS 파일 읽는 중: {wbs_file_path}")
        try:
            excel_file = pd.ExcelFile(wbs_file_path, engine='openpyxl')
        except Exception as e:
            print(f"'{wbs_file_path}' 파일 로드 시 openpyxl 엔진 사용 중 오류: {e}. 기본 엔진으로 재시도합니다.")
            excel_file = pd.ExcelFile(wbs_file_path) # 기본 엔진으로 시도

        if not excel_file.sheet_names:
            raise ValueError(f"엑셀 파일에 시트가 없습니다: {wbs_file_path}")
        
        df = excel_file.parse(excel_file.sheet_names[0])
        
        print(f"WBS 파일 (시트: {excel_file.sheet_names[0]}) 상위 3개 행:\n{df.head(3)}")
        print("WBS 파일 읽기 완료. JSON으로 변환 중...")
        
        wbs_json = df.to_json(orient='records', indent=None, force_ascii=False, date_format='iso')
        return wbs_json
    except FileNotFoundError:
        print(f"오류: WBS 파일을 읽을 수 없습니다 - {wbs_file_path}")
        raise
    except ValueError as ve:
        print(f"WBS 파일 처리 중 값 오류: {ve}")
        raise
    except Exception as e:
        print(f"WBS 파일 읽기 또는 JSON 변환 오류 ({wbs_file_path}): {e}")
        raise
