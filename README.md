# FAA美食自动助理 FoodsVsMouses_AutoAssistant

《美食大战老鼠》的自动助手，一键完成所有日常。
An automatic assistant for Foods vs. Mice, complete all daily tasks with one click.

本软件基于图像识别 + 自动放置卡片完成战斗，不支持任何作弊功能（如秒杀）。
This software is based on image recognition and automatic card placement for battles, and does not support any cheating functions (such as instant kills).

本软件历经一年开发，已趋近成熟，功能完善且丰富。
This software has been in development for a year and is now approaching maturity with comprehensive and rich features.

该工具开发初衷是圆梦十年前的童年愿望 (悲)
The original intention of developing this tool is to fulfill a childhood wish from ten years ago (XD)

# 主页 | Home

[FAA - 网络文档](https://stareabyss.github.io/FAA-WebSite/)  包括了功能综述, 新手入门教程, 进阶介绍, 开发文档.

文档主体搬迁至该网站, 并逐步施工中... 此页面部分重复内容不再保留.

# 下载 | Download [![](https://img.shields.io/github/downloads/StareAbyss/FoodsVsMiceAutoAssistant/total?color=4e4c97)](https://github.com/StareAbyss/FoodsVsMiceAutoAssistant/releases)

* Github-Release 
  * 包含FAA的稳定发行版, 不包含不稳定的测试版本.
  * 点击上方按钮跳转. 找到最新的版本, 找到最新的版本, 下滑过更新介绍, 找到下方的.zip文件, 解压后开袋即食.
  * 此项目的源码会实时更新, 仅不发布测试打包版本.
* 交流QQ群-群文件
  * 包含FAA的稳定发行版和内部测试版(beta).
  * 更有玩家社区维护的大量战斗方案供您使用.

# 关于 | About

![](https://img.shields.io/badge/QQ%201群-786921130-4e4c97) 1500/2000人 推荐加入

![](https://img.shields.io/badge/QQ%202群-142272678-4e4c97) 1500/2000人 推荐加入

爱发电赞助支持FAA - 爱发电因备案过期暂时无法访问! 暂时终止使用!  

微信赞赏码支持FAA - 请扫码下图  

<img alt="image" height="300" src="md_img/FAA-赞赏码.jpg" width="300"/>

# 预览 | Preview

## 运行主页  

![image](md_img/运行主页.png)

## 流程配置  

![image](md_img/任务列表.png)

## 高级选项  

![image](md_img/高级功能.png)

## 战斗方案编辑器  

![image](md_img/战斗方案编辑器.png)

# 功能 | Feature

* 自动日常- 非战斗类流程
  * 日常打卡
    * VIP - 每日签到 & 礼卷领取
    * 每日签到
    * 美食活动 - 每日免费许愿
    * 寻宝塔罗 & 法老宝藏 - 免费抽取
    * 公会 - 会长发布公会任务
    * 公会 - 花园浇水 / 施肥 / 摘果
  * 自动领取所有类型任务奖励, 包括: 普通任务/公会任务/情侣任务/悬赏任务/美食大赛/大富翁/营地任务
  * 自动使用消耗品
    * 可自定义删除对象
  * 自动删除无用道具
    * 默认主要是技能书. 需要高级设置 - 设定二级密码. 可自定义删除对象
  * 公会副本商店 - 兑换暗晶.
    * 需要高级设置 - 设定二级密码
* 流水线刷本 - 战斗类流程
  * 自动任务 
    * 双人 公会任务
    * 双人 情侣任务
    * 双人 悬赏任务
    * 美食大赛(战令任务), 基于特制OCR和语义识别, 超强执行力, 确保完成.
  * 常规刷本
    * 自定义单本连刷 轻松打完45把每日. 支持所有副本的自动进出!
    * 勇士本 火山遗迹 跨服副本 战斗预设, 轻松搞定.
  * 魔塔蛋糕
    * 单人魔塔, 支持双线程
    * 双人魔塔
    * 魔塔密室, 支持双线程
  * 自定义任务序列
    * 接口开放, 可完全自定义的任务列表. 支持更多参数和自定义顺序.
    * 支持使用任务序列可视化编辑器进行编写.
  * 支持无限跨服副本刷威望
* 自动放卡战斗
  * 模仿人类思考方式的算法实现, 从目标阵容和卡片与位置重要性角度进行合理放卡.
  * 单人双人均可支持.
  * 方案系统
    * 上手轻松, 可高度自定义的战斗方案
    * 下限高, 上限足. 大量内置方案, 轻松上手入门, 攻略各种高难副本, 魔塔164 / 天妇罗 / 音乐节夜 均不在话下.
    * Json格式, 便于分享您的奇思, 获取他人的妙想.
    * 内置战斗方案编辑器, 超轻松快捷可视化编辑, 无需写代码.
  * 超强自动化
    * 自动 承载卡
      * 仅需将对应卡片放入卡组中, 无需在战斗方案进行额外设置, 即可根据关卡自适应放置.
      * 支持从米苏物流获取最新承载卡资源, 无需软件更新.
    * 自动 极寒冰沙, 仅需将对应卡片放入卡组中, 无需在战斗方案进行额外设置, 即可根据战况自适应放置.
    * 自动 幻幻鸡 / 创造神, 仅需将对应卡片放入卡组中, 仅需在战斗方案设置各卡片被复制的优先级, 即可根据战况, 自适应放置完成复制.
    * 自动使用武器技能.
    * 自动鼠标模拟拾取.
  * 高级战斗 - beta
    * 基于深度学习的图像识别 + 线性规划的高级战斗功能.
    * 实现自动使用对策牌, 解决高危目标和场地机制. 
* 其他特性
  * 无限跨服一分钟刷威望.
  * 自动定时启动, 真正做到设置一次, 点击一下, 自动刷一周!
  * 公会管理器! 自动扫描每周贡献值!
  * 战利品和开宝箱记录
    * 精准图像识别, 自动纠错, 保存历史记录.
    * 上传至[美食数据站 - FAA米苏物流](https://faa.msdzls.cn/)统计副本掉率.

# 免责声明 | Disclaimer

* 本软件使用 [AGPL 3.0 协议](https://github.com/StareAbyss/FoodsVsMiceAutoAssistant/blob/main/LICENSE)开源.
  * 免费, 仅供学习交流使用. 
  * 若您遇到商家使用本软件进行代练并收费, 可能是设备与时间等费用, 产生的问题及后果与本软件无关.
* 请不要使用非最新版本的FAA进行游戏 , 初次执行过程中建议 **<关注执行情况>** 
* 若执行中因bug导致任何问题, 请立刻 **<刷新游戏窗口>** + **<叉掉退出软件>**, 本人不负任何法律责任.
* 再次说明 防bug损失建议:
    * **<设定二级密码 + 使用中不输入>**
    * **<有一定的礼卷防翻牌异常>**
    * **<高星不绑卡挂拍卖/提前转移>**

# 致谢 | Acknowledgments

* 图像识别：[opencv](https://github.com/opencv/opencv.git)
* 图形化界面：[PyQt6](https://github.com/PyQt6/PyQt6.git)
* 文档构筑：[vue-press](https://github.com/vuepress)
* 感谢交流群的各位小伙伴对本软件的测试和相关建议 ~ 
* 详细的致谢内容, 参见[致谢名单.md](https://github.com/StareAbyss/FoodsVsMiceAutoAssistant/blob/main/%E8%87%B4%E8%B0%A2%E5%90%8D%E5%8D%95.md)
