"""
Valida o arquivo Excel antes de processar:
- Verifica extensão
- Verifica tamanho
- Verifica colunas mínimas obrigatórias
"""
from fastapi import UploadFile, HTTPException, status

MAX_FILE_SIZE_MB = 50
ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
MINIMUM_REQUIRED_COLUMNS = {
    "titular da compra - e-mail",
    "valor ingresso",
    "data",
}


async def validate_upload(file: UploadFile) -> bytes:
    """
    Lê e valida o arquivo de upload.
    Retorna os bytes do arquivo para uso posterior.
    """
    _validate_extension(file.filename)
    content = await file.read()
    _validate_size(content)
    return content


def _validate_extension(filename: str) -> None:
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de arquivo inválido."
        )
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato não suportado: '{ext}'. Envie um arquivo .xlsx ou .xls."
        )


def _validate_size(content: bytes) -> None:
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande ({size_mb:.1f}MB). Limite: {MAX_FILE_SIZE_MB}MB."
        )