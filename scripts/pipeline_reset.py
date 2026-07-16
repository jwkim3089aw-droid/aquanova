# scripts/pipeline_reset.py
import os
import sys
import shutil
import logging

# CMD 터미널 전용 로깅 시스템 설정
logger = logging.getLogger("Pipeline_Reset")
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


def reset_pipeline():
    """마스터 DB 파일 삭제 및 격리/보관 폴더의 PDF 파일을 INPUT 폴더로 원상복구"""
    base_dir = "./WAVE_PIPELINE"
    dir_input = os.path.join(base_dir, "1_INPUT")
    dir_completed = os.path.join(base_dir, "2_COMPLETED")
    dir_failed = os.path.join(base_dir, "3_FAILED")

    db_json = "./.data/wave_extracted_dataset.json"
    db_csv = "./.data/wave_extracted_dataset.csv"

    logger.info("============================================================")
    logger.info(" AquaNova 데이터 파이프라인 통합 초기화(Reset) 프로세스 가동")
    logger.info("============================================================")

    # 1. 마스터 DB 파일 삭제
    for db_file in [db_json, db_csv]:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                logger.info(
                    f"[DB 삭제] 기존 마스터 데이터 파일이 제거되었습니다: {db_file}"
                )
            except Exception as e:
                logger.error(f"[DB 에러] 파일 삭제 실패 ({db_file}): {e}")

    # 2. 작업용 필수 폴더 존재 여부 확인 및 생성
    for directory in [dir_input, dir_completed, dir_failed]:
        os.makedirs(directory, exist_ok=True)

    # 3. COMPLETED 폴더의 파일들을 INPUT 폴더로 복구
    completed_files = [
        f for f in os.listdir(dir_completed) if f.lower().endswith(".pdf")
    ]
    if completed_files:
        logger.info(
            f"[인양 작업] 보관소(2_COMPLETED)의 파일 {len(completed_files)}개를 작업대(1_INPUT)로 재배치합니다."
        )
        for f_name in completed_files:
            shutil.move(
                os.path.join(dir_completed, f_name), os.path.join(dir_input, f_name)
            )

    # 4. FAILED 폴더의 파일들을 INPUT 폴더로 복구
    failed_files = [f for f in os.listdir(dir_failed) if f.lower().endswith(".pdf")]
    if failed_files:
        logger.info(
            f"[인양 작업] 격리소(3_FAILED)의 파일 {len(failed_files)}개를 작업대(1_INPUT)로 재배치합니다."
        )
        for f_name in failed_files:
            shutil.move(
                os.path.join(dir_failed, f_name), os.path.join(dir_input, f_name)
            )

    logger.info("============================================================")
    logger.info(" 파이프라인 초기화 완료. 이제 파서(Parser)를 다시 구동하시면 됩니다.")
    logger.info("============================================================")


if __name__ == "__main__":
    reset_pipeline()
