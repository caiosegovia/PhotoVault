@echo off
setlocal enabledelayedexpansion
title PhotoVault - Build .exe
color 0A

echo.
echo  ======================================
echo    PhotoVault - Compilador Windows
echo  ======================================
echo.

:: Verificar se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERRO] Python nao encontrado no PATH!
        echo.
        echo  Instale o Python em: https://www.python.org/downloads/
        echo  Marque "Add Python to PATH" durante a instalacao.
        echo.
        pause
        exit /b 1
    )
    set PYTHON=py
) else (
    set PYTHON=python
)

for /f "tokens=*" %%i in ('!PYTHON! --version') do set PYVER=%%i
echo [OK] %PYVER% encontrado.

:: Navegar para a pasta do script
cd /d "%~dp0"
echo [OK] Pasta: %CD%

:: Criar venv se nao existir
if not exist ".venv_win" (
    echo.
    echo [1/4] Criando ambiente virtual...
    !PYTHON! -m venv .venv_win
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv.
        pause
        exit /b 1
    )
    echo [OK] Venv criado.
) else (
    echo [OK] Venv ja existe.
)

:: Ativar venv
call .venv_win\Scripts\activate.bat

:: Atualizar pip
echo.
echo [2/4] Atualizando pip...
python -m pip install --upgrade pip --quiet

:: Instalar dependencias
echo.
echo [3/4] Instalando dependencias...
echo       (pode demorar alguns minutos na primeira vez)
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERRO] Falha ao instalar PyInstaller.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.

:: Matar processo anterior se estiver rodando
echo.
echo [4/4] Compilando PhotoVault.exe...
taskkill /f /im PhotoVault.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Renomear dist anterior (renomear nao trava arquivos protegidos pelo Defender)
if exist "dist\PhotoVault" (
    if exist "dist\PhotoVault_old" rmdir /s /q "dist\PhotoVault_old" >nul 2>&1
    rename "dist\PhotoVault" "PhotoVault_old" >nul 2>&1
)
if exist "build\PhotoVault" rmdir /s /q "build\PhotoVault" >nul 2>&1

:: Rodar PyInstaller
pyinstaller photovault.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo [ERRO] Falha na compilacao. Veja os erros acima.
    pause
    exit /b 1
)

:: Resultado
echo.
echo  ======================================
echo    BUILD CONCLUIDO COM SUCESSO!
echo  ======================================
echo.
echo  Executavel gerado em:
echo    %CD%\dist\PhotoVault\PhotoVault.exe
echo.

:: Abrir pasta do executavel
explorer "%CD%\dist\PhotoVault"

pause
