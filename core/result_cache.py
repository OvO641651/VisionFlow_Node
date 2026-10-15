# -*- coding: utf-8 -*-
"""
结果缓存的上限与 LRU 淘汰（批次5 目标4；**纯逻辑、零 Qt**）

## 背景 / 现状（2026.10.15 实测）

`self.result_cache` 是个普通 dict：键 = `_result_cache_key(图片标识, 执行方式)`，
值 = `{"frame": 处理后的整幅图, "data": 检测数据, "exec_info": 日志}`，作用 = **切回某张图时直接显示上次结果、不用再执行**。

原来只有**一处**"上限"（写在 `core/flow_engine.py` 的**视频分支**里）：

    # 结果缓存加个上限（尾巴之二，2026.10.7 补）：视频逐帧跑会不断新增键，
    # 超过 400 条就把最旧的丢掉（FIFO 近似 LRU），免得越跑越吃内存。
    if len(self.result_cache) > 400:
        for old_key in list(self.result_cache)[:-400]:
            self.result_cache.pop(old_key, None)

它有三个毛病：
1. **是 FIFO 近似 LRU** —— 命中缓存（`_show_static_image`）时**不刷新顺序** ⇒ "**刚看过的图照样被淘汰**"；
2. 按**条数**而不是按**内存** —— 实测小图 0.75 MB/条、大图（2000×1000）5.72 MB/条，
   同样 400 条可以是 378 MB、也可以是 2.3 GB；
3. **只对视频路径生效** ⇒ **静态图批量跑（"运行全部"）其实没有任何上限**。

## 本模块做什么（用户 2026.10.15 拍板）

把上限做成**统一的两池 LRU**：

| 池 | 装什么 | 上限（条数 + 字节双条件） |
|---|---|---|
| **静态池** | 静态图片 / 各页面（键 = 图片路径或标识） | `STATIC_MAX_ITEMS` 条（400）+ `STATIC_MAX_BYTES` 字节（256 MB） |
| **序列池** | 视频逐帧（键形如 `路径#帧号`） | `SEQUENCE_MAX_ITEMS` 条（120）+ `SEQUENCE_MAX_BYTES` 字节（64 MB） |

**为什么要分池**：视频帧每帧一条、而且"刚用过"，统一一个 LRU 池的话**看一段视频就会把静态图结果全挤掉**。

**命中即"移到最新"**（`touch()`）：读取缓存时把该键 `cache[k] = cache.pop(k)`（O(1)），
超限时淘汰的是**最久没用过**的那条 —— 这才是真 LRU。
**淘汰不影响正确性**：被淘汰的图下次要用就重算，结果逐像素一致（用例 `dsh_t5g4_cache_check` 钉死这一点）。
**相机帧仍然不进缓存**（既有规矩，不在本模块职责内）。
"""

# ---------------------------------------------------------------- 上限（可用例临时改小来验证）
STATIC_MAX_ITEMS = 400
STATIC_MAX_BYTES = 256 * 1024 * 1024          # 256 MB
SEQUENCE_MAX_ITEMS = 120                      # 约 4 秒 @30fps
SEQUENCE_MAX_BYTES = 64 * 1024 * 1024         # 64 MB


def is_sequence_key(cache_key):
    """
    这个缓存键是不是"视频逐帧"那一类？

    判据 = 图片标识里带 `#`（`core/param_store.py::_image_key_of` 给视频帧的键就是
    `"{video_path}#{帧号}"`；静态图是文件路径、兜底是标识字符串，都不含 `#`）。
    """
    try:
        image_key = cache_key[0]
    except Exception:
        return False
    return isinstance(image_key, str) and "#" in image_key


def frame_bytes(entry):
    """一条缓存占的近似内存（只算那张处理后的图；data / exec_info 都很小）"""
    frame = (entry or {}).get("frame")
    return int(getattr(frame, "nbytes", 0) or 0)


def touch(cache, cache_key):
    """
    **命中缓存时调用**：把这个键移到 dict 末尾（= "最近用过"）。O(1)，不影响值。

    这一步是真 LRU 与"FIFO 近似"的唯一区别 —— 少了它，刚看过的图照样会被当成最旧的丢掉。
    """
    if cache_key in cache:
        cache[cache_key] = cache.pop(cache_key)


def pool_stats(cache):
    """给用例 / 日志用：两个池各自的（条数, 字节）"""
    out = {"static": [0, 0], "sequence": [0, 0]}
    for key, entry in cache.items():
        bucket = out["sequence"] if is_sequence_key(key) else out["static"]
        bucket[0] += 1
        bucket[1] += frame_bytes(entry)
    return {name: (count, size) for name, (count, size) in out.items()}


def evict(cache):
    """
    按两个池各自的"条数 + 字节"上限淘汰**最久没用过**的条目（dict 顺序 = 从旧到新）。

    :param cache: `self.result_cache`（普通 dict；本函数**原地**修改它）
    :return: 被丢掉的键列表（按丢弃顺序；调用方可据此写日志 / 断言）
    """
    limits = ((False, STATIC_MAX_ITEMS, STATIC_MAX_BYTES),
              (True, SEQUENCE_MAX_ITEMS, SEQUENCE_MAX_BYTES))
    removed = []
    for want_sequence, max_items, max_bytes in limits:
        keys = [k for k in cache if is_sequence_key(k) is want_sequence]
        total = sum(frame_bytes(cache[k]) for k in keys)
        index = 0
        while keys[index:] and (len(keys) - index > max_items or total > max_bytes):
            old_key = keys[index]
            total -= frame_bytes(cache[old_key])
            cache.pop(old_key, None)
            removed.append(old_key)
            index += 1
    return removed
