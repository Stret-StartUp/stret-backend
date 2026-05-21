from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.security import create_access_token
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    """
    Endpoint para registrar um novo usuário.
    
    - **email**: Email do usuário (único)
    - **password**: Senha do usuário (será criptografada)
    - **full_name**: Nome completo (opcional)
    """
    repo = UserRepository(db)
    
    # Verificar se o email já existe
    existing_user = await repo.get_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já cadastrado",
        )
    
    # Criar novo usuário
    user = await repo.create(
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
    )
    
    return user


@router.post("/login", response_model=Token)
async def login(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """
    Endpoint para fazer login.
    
    - **email**: Email do usuário
    - **password**: Senha do usuário
    
    Retorna um token JWT para autenticação em outros endpoints.
    """
    repo = UserRepository(db)
    
    # Autenticar usuário
    user = await repo.authenticate(user_data.email, user_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )
    
    # Criar token de acesso
    access_token = create_access_token(subject=str(user.id))
    
    return Token(access_token=access_token, token_type="bearer")
