from fastapi import APIRouter, Body
from app.libs.llm import llm_generate
from app.libs.form import make_query, safe_json_load
from app.libs.exceptions import UnprocessableEntityException
from app.libs.docx import word_generate
from app.libs.pdf import convert_to_pdf
import os
import json
import logging
import traceback
from app.libs.mail import sendEmail

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "generate_errors.log")

router = APIRouter()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

@router.post("/generate")
def generate_complaints(payload: dict = Body(...)):
    llm_result = None
    try:
        combined = payload["combined_data"]
        
        form_data = {}
        for section in combined.values():
            if isinstance(section, dict):
                for k, v in section.items():
                    if isinstance(v, str):
                        form_data[k] = v.replace("\t", " ").replace("\r", " ").replace("\n", " ")
                    else:
                        form_data[k] = v
        
        keys_to_remove = ['고소인', '고소인 주민등록번호', '고소인 주소', '고소인 직업', '고소인 전화', '고소인 이메일',
                          '피고소인', '피고소인 주민등록번호', '피고소인 주소', '피고소인 직업', '피고소인 전화',
                          '사용자 이메일', '제출용 이메일']
        llm_input_form = {k: v for k, v in form_data.items() if k not in keys_to_remove}
        
        llm_result, model_name = llm_generate(make_query(llm_input_form))
        try:
            safe_json = safe_json_load(llm_result)
            result_data = json.loads(safe_json)
        except:
            raise UnprocessableEntityException("LLM response is not a valid JSON")
        
        
        docx_path = word_generate(result_data, form_data)
        pdf_path = convert_to_pdf(docx_path)
        
        user_email = form_data.get("사용자 이메일","")
        if user_email:
            try:
                mail_title = "[PAILAB AI 고소장] 고소장이 생성되었습니다"
                mail_text = """
안녕하세요.
요청하신 AI 고소장 파일 생성이 완료되어 송부드립니다.

첨부된 문서는 AI를 통해 생성된 초안입니다.
제출 전 반드시 사실관계와 법률 용어를 다시 한번 검토해 주시기 바랍니다.

감사합니다.
"""
                sendEmail(user_email, mail_title, mail_text, str(docx_path))

            except Exception as e:
                logging.error(f"Failed to send email to {user_email}: {str(e)}")
        
        submit_email = form_data.get("제출용 이메일","")   
        if submit_email:
            try:
                mail_title_target = f"[PAILAB AI 고소장 제출] {form_data.get('고소인', '')}님의 고소장입니다."
                mail_text_target = f"""
{form_data.get('고소인', '')}님의 AI 고소장을 송부합니다.
첨부파일을 확인해 주시기 바랍니다.
"""
                sendEmail(submit_email, mail_title_target, mail_text_target, str(docx_path))
            except Exception as e:
                logging.error(f"Failed to send submission email to {submit_email}: {str(e)}")

        return {
            "file_id": docx_path.stem,
            "preview_pdf": f"/preview/pdf/{docx_path.stem}",
            "download_word": f"/download/word/{docx_path.stem}",
            "download_pdf": f"/download/pdf/{docx_path.stem}",
            "model_name": model_name,
            "model_url": f"https://huggingface.co/{model_name}"
        }
    except Exception as e:
        logging.error(
            (
                "Exception occurred\n"
                f"Exception: {str(e)}\n\n"
                "LLM Response:\n"
                f"{safe_json}\n\n"
                "Traceback:\n"
                f"{traceback.format_exc()}"
            )
        )

        raise UnprocessableEntityException(str(e))
    
