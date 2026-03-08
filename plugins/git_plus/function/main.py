from GitSDK import git_by_ini


def main():
    # 从 dev_config.ini 读取配置并执行异步获取 git log
    result = git_by_ini(use_dev=True, async_mode=True, operation='get_git_log')
    
    # 打印结果
    if result:
        print(f"\n共获取到 {len(result)} 条 Git 日志记录:\n")
        for i, log in enumerate(result, 1):
            print(f"[{i}] {log.commit_hash[:8]} - {log.message}")
            print(f"    Author: {log.author}")
            print(f"    Date:   {log.date}\n")
    else:
        print("No git log information available")


if __name__ == '__main__':
    main()