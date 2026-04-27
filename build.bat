@echo off
REM 1. Inject the STM32 Compiler and Make tool paths, plus the existing Windows PATH
set "PATH=C:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.gnu-tools-for-stm32.13.3.rel1.win32_1.0.0.202411081344\tools\bin;C:\ST\STM32CubeIDE_1.19.0\STM32CubeIDE\plugins\com.st.stm32cube.ide.mcu.externaltools.make.win32_2.2.0.202409170845\tools\bin;%PATH%"

REM 2. Navigate exactly to where the makefile is located
cd /d "C:\Users\kerem\Documents\ImbedderNewTrial_MAI\BSP\BSP\STM32CubeIDE\Debug"

REM 3. Execute the build process
echo Building the project...
make all