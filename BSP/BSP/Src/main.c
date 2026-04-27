/**
  ******************************************************************************
  * @file    Examples/BSP/Src/main.c
  * @author  MCD Application Team
  * @brief   Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2021 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "b_u585i_iot02a_bus.h"
#include "b_u585i_iot02a_motion_sensors.h"
#include "b_u585i_iot02a_env_sensors.h"
#include "b_u585i_iot02a_ranging_sensor.h"

/* Private variables --------------------------------------------------------*/
BSP_MOTION_SENSOR_Axes_t accel_axes;
float temp_value;
RANGING_SENSOR_Result_t tof_distance;
RANGING_SENSOR_ProfileConfig_t tof_profile;

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void CACHE_Enable(void);

/**
  * @brief  Main program
  */
void SystemInit(void);

int main(void)
{
  /* Call the system MSP init FIRST (this is what the original does) */
  SystemInit();

  /* Minimal stack init - just set SP */
  __HAL_RCC_PWR_CLK_ENABLE();
  HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1);
  HAL_PWREx_ConfigSupply(PWR_SMPS_SUPPLY);
  __HAL_RCC_PWR_CLK_DISABLE();

  /* System clock */
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_MSI;
  RCC_OscInitStruct.MSIState = RCC_MSI_ON;
  RCC_OscInitStruct.MSIClockRange = RCC_MSIRANGE_4;
  RCC_OscInitStruct.MSICalibrationValue = RCC_MSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_MSI;
  RCC_OscInitStruct.PLL.PLLMBOOST = RCC_PLLMBOOST_DIV1;
  RCC_OscInitStruct.PLL.PLLM = 1;
  RCC_OscInitStruct.PLL.PLLN = 80;
  RCC_OscInitStruct.PLL.PLLR = 2;
  RCC_OscInitStruct.PLL.PLLP = 2;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLFRACN = 0;
  HAL_RCC_OscConfig(&RCC_OscInitStruct);
  RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2 | RCC_CLOCKTYPE_PCLK3);
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;
  RCC_ClkInitStruct.APB3CLKDivider = RCC_HCLK_DIV1;
  HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_4);

  /* ICACHE */
  HAL_ICACHE_ConfigAssociativityMode(ICACHE_1WAY);
  HAL_ICACHE_Enable();

  /* LED init */
  __HAL_RCC_GPIOH_CLK_ENABLE();
  GPIO_InitTypeDef led = {0};
  led.Pin = GPIO_PIN_7;
  led.Mode = GPIO_MODE_OUTPUT_PP;
  led.Pull = GPIO_NOPULL;
  led.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOH, &led);

  /* Blink LED to show we reached main */
  for (int i = 0; i < 5; i++) {
    HAL_GPIO_TogglePin(GPIOH, GPIO_PIN_7);
    for (volatile int d = 0; d < 500000; d++);
  }

  /* UART4 init */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_UART4_CLK_ENABLE();
  GPIO_InitTypeDef gpio_u4 = {0};
  gpio_u4.Pin = GPIO_PIN_10 | GPIO_PIN_11;
  gpio_u4.Mode = GPIO_MODE_AF_PP;
  gpio_u4.Pull = GPIO_NOPULL;
  gpio_u4.Speed = GPIO_SPEED_FREQ_HIGH;
  gpio_u4.Alternate = GPIO_AF8_UART4;
  HAL_GPIO_Init(GPIOC, &gpio_u4);
  UART_HandleTypeDef huart4 = {0};
  huart4.Instance = UART4;
  huart4.Init.BaudRate = 115200;
  huart4.Init.WordLength = UART_WORDLENGTH_8B;
  huart4.Init.StopBits = UART_STOPBITS_1;
  huart4.Init.Parity = UART_PARITY_NONE;
  huart4.Init.Mode = UART_MODE_TX_RX;
  huart4.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart4.Init.OverSampling = UART_OVERSAMPLING_16;
  huart4.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart4.Init.ClockPrescaler = UART_PRESCALER_DIV1;
  HAL_UART_Init(&huart4);

  /* USART1 init */
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_USART1_CLK_ENABLE();
  GPIO_InitTypeDef gpio_u1 = {0};
  gpio_u1.Pin = GPIO_PIN_9 | GPIO_PIN_10;
  gpio_u1.Mode = GPIO_MODE_AF_PP;
  gpio_u1.Pull = GPIO_NOPULL;
  gpio_u1.Speed = GPIO_SPEED_FREQ_HIGH;
  gpio_u1.Alternate = GPIO_AF7_USART1;
  HAL_GPIO_Init(GPIOA, &gpio_u1);
  UART_HandleTypeDef huart1 = {0};
  huart1.Instance = USART1;
  huart1.Init.BaudRate = 115200;
  huart1.Init.WordLength = UART_WORDLENGTH_8B;
  huart1.Init.StopBits = UART_STOPBITS_1;
  huart1.Init.Parity = UART_PARITY_NONE;
  huart1.Init.Mode = UART_MODE_TX_RX;
  huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart1.Init.OverSampling = UART_OVERSAMPLING_16;
  huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart1.Init.ClockPrescaler = UART_PRESCALER_DIV1;
  HAL_UART_Init(&huart1);

  /* ToF sensor init first (uses I2C2, must init before accel/temp on I2C1) */
  int32_t tof_err = BSP_RANGING_SENSOR_Init(VL53L5A1_DEV_CENTER);
  tof_profile.RangingProfile = RS_PROFILE_4x4_CONTINUOUS;
  tof_profile.TimingBudget = 30;
  tof_profile.Frequency = 5;
  tof_profile.EnableAmbient = 0;
  tof_profile.EnableSignal = 0;
  BSP_RANGING_SENSOR_ConfigProfile(VL53L5A1_DEV_CENTER, &tof_profile);
  BSP_RANGING_SENSOR_Start(VL53L5A1_DEV_CENTER, RS_MODE_BLOCKING_CONTINUOUS);

  /* Accel init */
  BSP_MOTION_SENSOR_Init(0, MOTION_ACCELERO);
  BSP_MOTION_SENSOR_Enable(0, MOTION_ACCELERO);

  /* Temp sensor init (HTS221 on instance 0) */
  BSP_ENV_SENSOR_Init(0, ENV_TEMPERATURE);
  BSP_ENV_SENSOR_Enable(0, ENV_TEMPERATURE);

  uint8_t msg[64];
  int len = snprintf((char *)msg, sizeof(msg), "ToF Init: %ld | Accel OK | Temp OK\r\n", (long)tof_err);
  HAL_UART_Transmit(&huart4, msg, len, HAL_MAX_DELAY);
  HAL_UART_Transmit(&huart1, msg, len, HAL_MAX_DELAY);

  /* Main loop */
  while (1)
  {
    BSP_MOTION_SENSOR_GetAxes(0, MOTION_ACCELERO, &accel_axes);
    BSP_ENV_SENSOR_GetValue(0, ENV_TEMPERATURE, &temp_value);
    BSP_RANGING_SENSOR_GetDistance(VL53L5A1_DEV_CENTER, &tof_distance);
    len = snprintf((char *)msg, sizeof(msg), "Accel: X=%d Y=%d Z=%d | Temp: %.1f C | ToF: %ld mm\r\n",
                   accel_axes.xval, accel_axes.yval, accel_axes.zval, temp_value,
                   (long)tof_distance.ZoneResult[0].Distance[0]);
    HAL_UART_Transmit(&huart4, msg, len, HAL_MAX_DELAY);
    HAL_UART_Transmit(&huart1, msg, len, HAL_MAX_DELAY);
    HAL_GPIO_TogglePin(GPIOH, GPIO_PIN_7);
    HAL_Delay(500);
  }
}

void SystemClock_Config(void) {}

/**
  * @brief  Enable ICACHE
  */
static void CACHE_Enable(void)
{
  HAL_ICACHE_ConfigAssociativityMode(ICACHE_1WAY);
  HAL_ICACHE_Enable();
}

void Error_Handler(void)
{
  while (1) { HAL_GPIO_TogglePin(GPIOH, GPIO_PIN_6); for(volatile int d=0;d<100000;d++); }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line) {}
#endif
