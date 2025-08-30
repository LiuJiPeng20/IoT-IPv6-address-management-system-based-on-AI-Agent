# **基于AI Agent的物联网IPv6地址管理系统**功能说明

## 1.项目概述

这是一个用于物联网设备IPv6地址分配和管理的系统，主要解决IoT设备的IPv6地址自动分配、设备审批流程和与KEA DHCP服务器的API集成问题。

## 2.项目架构

### 技术栈

- 后端: Django 3.2.9 + Python

- 数据库: MySQL (ipv6数据库)

- 前端: Bootstrap 3.4.1 + jQuery 3.6.0

- 中间件: 自定义认证中间件

- 外部集成: KEA DHCP API

### 核心模块组织

app01/
├── models.py          # 数据模型层
├── views/            # 视图层
│   ├── account.py    # 用户认证
│   ├── admin.py      # 管理员管理
│   ├── depart.py     # 部门管理
│   ├── device.py     # 设备管理
│   ├── device_approval.py  # 设备审批
│   ├── pretty.py     # IPv6地址管理
│   └── user.py       # 用户管理
├── utils/            # 工具库
│   ├── ipv6_api.py   # KEA API集成
│   ├── ipv6_generator.py  # IPv6地址生成算法
│   ├── form.py       # 表单处理
│   ├── pagination.py # 分页组件
│   └── encrypt.py    # 加密工具
└── middleware/       # 中间件
    └── auth.py       # 认证中间件

## 3.核心功能模块

### 1. 用户认证与权限管理

- 双重身份系统: 管理员(Admin) + 普通用户(UserInfo)

- 会话管理: 基于Django Session的用户状态维护

- 权限控制: 自定义中间件实现路由级权限控制

- 差异化界面: 管理员和普通用户看到不同的操作界面

### 2. 设备审批工作流

- 申请提交: 用户填写设备信息(DUID、MAC、部门、楼栋、业务类型)

- 管理员审批: 支持同意/拒绝操作

- 自动设备创建: 审批通过后自动创建Device记录

- 状态追踪: 实时显示审批状态

### 3. 与KEA DHCP API的Agent集成系统

这是项目的核心亮点，实现了与外部DHCP服务器的深度集成：

#### API发送机制

- 数据封装: 发送完整IPv6地址、MAC地址、DUID、时间戳等

- 回调设计: 支持异步回调处理绑定结果

- 容错处理: 10秒超时、连接错误处理

### 4.待完成.....



## 4.部分页面展示

### 1.登录页面

<img src="C:/Users/HP/AppData/Roaming/Typora/typora-user-images/image-20250829173023858.png" alt="image-20250829173023858" style="zoom:50%;" />

### 2.IPv6地址绑定页面

![image-20250829173312088](C:/Users/HP/AppData/Roaming/Typora/typora-user-images/image-20250829173312088.png)

