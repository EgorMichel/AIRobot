@startuml
!theme plain

skinparam componentStyle uml2
skinparam actorStyle awesome
skinparam packageStyle rect
skinparam linetype ortho
skinparam shadowing false

' ===== Цвета слоёв =====
skinparam package<<voice>> {
  BackgroundColor #E3F2FD
  BorderColor #90CAF9
}

skinparam package<<mode>> {
  BackgroundColor #FFF9C4
  BorderColor #FBC02D
}

skinparam package<<core>> {
  BackgroundColor #E8F5E9
  BorderColor #81C784
}

skinparam package<<hardware>> {
  BackgroundColor #F5F5F5
  BorderColor #BDBDBD
}

skinparam component<<hardware>> {
  FontSize 10
}

' ===== Внешние сущности =====
actor "Пользователь" as User
database "LLM API" as LLM_API

' ===== Основная система =====
package "Роботизированный Голосовой Агент" {

  ' --- Voice ---
  package "Ввод / Вывод (voice)" <<voice>> {
    [ASR\n(Ввод речи)] as ASR
    [TTS\n(Вывод речи)] as TTS
  }

  ' --- Mode ---
  package "Оркестратор" <<mode>> {
    [LLMMode] as Mode
  }

  ' --- Core ---
  package "Ядро Агента" <<core>> {
    [LLMAgent] as Agent
    [SkillExecutor] as Executor
    [RobotTools] as Tools
  }

  ' --- Hardware ---
  package "Абстракция Оборудования" <<hardware>> {
    component "IRobotDriver" as IDriver <<hardware>>
    component "IKinematics" as IKinematics <<hardware>>
    component "IServo" as IServo <<hardware>>
  }
}

' ===== Пользователь <-> Система =====
User -> ASR
TTS -up-> User

' ===== Центральная роль LLMMode =====
ASR ..> Mode
Mode .up.> TTS
Mode -down-> Agent
Mode -down-> Executor

' ===== Взаимодействия внутри Ядра =====
Agent ..> LLM_API
Agent ..> Tools
Executor ..> Tools

' ===== Связи с оборудованием =====
Tools .down.> IDriver
Tools .down.> IKinematics
Tools .down.> IServo
@enduml