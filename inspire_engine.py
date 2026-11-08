"""灵感 AI 六维方案生成器（功能清单第 12-16 条）。

输入（主题，风格，痛点）→ 输出六维创意方案：
创意方向 / 风格建议 / 构图策略 / 配色方案（色卡+逻辑）/ 画面亮点 / 避坑清单 / 提示词
默认走本地规则引擎 build_plan；接入 DashScope 后 build_plan_ai 会用大模型
生成更贴合主题的方案，失败自动回退到 build_plan（签名与返回结构完全一致）。
"""
import ai_provider

STYLE_SWATCHES = {
    '扁平商业': ['#3E5BA3', '#75CBD1', '#F2D2FF', '#FFF6E9'],
    '三维写实': ['#5C6B73', '#9DB4C0', '#C24C4C', '#F5E9CF'],
    '国潮': ['#6E3377', '#F2D2FF', '#DAE8FB', '#0C0D45'],
    '极简': ['#F4F4F5', '#D9D9DE', '#3B4160', '#FF7B54'],
    '酸性': ['#A4A7E3', '#B6FF3D', '#6E3377', '#000229'],
    '涂鸦': ['#FFBE3D', '#F2453E', '#3B9B8F', '#1F1F38'],
    '像素': ['#80A4D4', '#9FE2EE', '#EAF7ED', '#2E5077'],
}

PAIN_FIX = {
    '风格同质化严重': '在主体风格骨架上混入一个异质元素（液态金属 / 故障边缘 / 反常规材质），同题材辨识度立即拉开，避开大路货',
    '构图缺乏张力': '放弃居中对称：主元素放大占画面 2/3，配一个极小对位元素，尺度对比的戏剧张力远超常规排版',
    '色彩搭配混乱': '收窄到三色体系：低饱和基底占 70%，主色 25%，高饱和点睛 5%，拒绝平均用力',
    '画面缺乏层次': '建立前中后三层：前景细节、中景主体、远景虚化色块，用明度差拉开距离',
    '创意概念平淡': '把命题从「描绘物」升级为「叙事瞬间」：呈现主题物被打破常规的瞬间，让观者先愣住、再读懂',
}


def build_plan(theme, style, pain):
    swatches = STYLE_SWATCHES.get(style, STYLE_SWATCHES['扁平商业'])
    return {
        'creative': ('把「%s」从平面命题升级为叙事命题：不直接描绘主题物，'
                     '而是呈现它被打破常规的瞬间，让观者先愣住、再读懂。'
                     '反同质化：%s' % (theme, PAIN_FIX.get(pain, PAIN_FIX['风格同质化严重']))),
        'style_rec': ('在「%s」骨架上混入一个异质元素（液态金属 / 故障边缘 / '
                      '反常规材质），同题材辨识度立即拉开，避开大路货' % style),
        'compose': ('放弃居中对称：主元素放大占画面 2/3，配一个极小对位元素，'
                    '尺度对比的戏剧张力远超常规排版'),
        'palette': {
            'swatches': swatches,
            'logic': '低饱和基底占 70%，主色 25%，高饱和点睛 5%，拒绝平均用力',
        },
        'highlight': ('设计一个「会被记住的细节」：一处鎏金纹理、一个反常规'
                      '小元素、或一处精心设计的负空间'),
        'pitfalls': [
            '别平均用力：焦点只有一个，其余全部做减法',
            '别堆元素：信息密度超过三层，画面立刻廉价',
            '别忽视留白：0.618 附近的呼吸感能救活整张稿子',
            '别照抄参考：借鉴结构逻辑，替换材质与色彩语言',
        ],
        'prompt': ('%s风格「%s」，尺度对比构图，主元素占2/3，'
                   '低饱和基底+5%%互补色点睛，留白呼吸感，'
                   '一个被记住的细节：%s。%s' % (
                       style, theme, '一处精心设计的负空间',
                       PAIN_FIX.get(pain, ''))),
    }


_AI_SYSTEM = (
    '你是一位有 15 年经验的资深视觉创意总监，先后服务于 4A 广告公司与头部'
    '互联网大厂的设计中台，专长是商业平面、品牌视觉与插画艺术指导，'
    '评审过数千份设计稿件。你的方案以「可直接落地」著称：每条建议都包含'
    '具体的技法参数或可执行动作，而不是抽象形容词。'
    '写作要求：使用设计师行业的专业术语（视觉锤、版式率、张力、负空间、'
    '色彩心理、视觉动线、层级、调性），像在给下属做创意 Brief 一样输出；'
    '禁止出现「高大上、美观、有设计感」这类空话。'
    '只输出一个 JSON 对象，不要任何解释文字或 markdown 代码块。'
)


def build_plan_ai(theme, style, pain):
    """用大模型生成六维创意方案；不可用或解析失败时回退 build_plan。"""
    if not ai_provider.is_enabled():
        return build_plan(theme, style, pain)
    swatches = STYLE_SWATCHES.get(style, STYLE_SWATCHES['扁平商业'])
    user_prompt = (
        '创作主题：%s\n目标风格：%s\n当前痛点：%s\n'
        '该风格参考色卡：%s\n\n'
        '请先在心里推断：这个主题的商业场景（海报/包装/IP/新媒体封面…）与'
        '目标受众，再据此输出方案。\n\n'
        '输出 JSON，字段严格如下（全部用中文，每条建议必须落到具体技法）：\n'
        '{"creative":"创意方向(80-150字)：先点明商业场景与受众，再给出核心创意'
        '概念与叙事钩子",'
        '"style_rec":"风格建议(60-120字)：风格骨架+异质化处理+材质/笔触/光效'
        '的具体选择",'
        '"compose":"构图策略(60-120字)：视角、主体占比、视觉动线、前中后层次、'
        '负空间安排",'
        '"palette":{"swatches":["#RRGGBB"共4个：基底色/主色/辅助色/点睛色，'
        '可微调参考色卡但须成体系],"logic":"配色逻辑(40-80字)：比例分配+'
        '色彩心理依据"},'
        '"highlight":"画面亮点(40-90字)：一个会被记住的细节，说清位置与做法",'
        '"pitfalls":["避坑1","避坑2","避坑3","避坑4"]（每条15-40字，针对该'
        '主题的典型翻车点），'
        '"prompt":"可直接投喂绘画模型的中文提示词(80-160字)：包含主题主体、'
        '风格与材质、构图与光线、色彩与氛围，按重要性排序，术语专业"}'
        % (theme, style, pain or '创意概念平淡', '、'.join(swatches)))
    data = ai_provider.chat_json(user_prompt, system=_AI_SYSTEM,
                                 temperature=0.7, max_tokens=2000)
    plan = _normalize_plan(data, style, swatches)
    if not plan:
        return build_plan(theme, style, pain)
    return plan


def _normalize_plan(data, style, fallback_swatches):
    """校验并规整大模型返回的 JSON，缺失字段用规则引擎兜底。"""
    if not isinstance(data, dict):
        return None
    base = build_plan('', style, '')
    pal = data.get('palette') if isinstance(data.get('palette'), dict) else {}
    sw = pal.get('swatches')
    if not (isinstance(sw, list) and len(sw) >= 3
            and all(isinstance(x, str) and x.startswith('#') for x in sw[:4])):
        sw = fallback_swatches
    pitfalls = data.get('pitfalls')
    if not (isinstance(pitfalls, list) and len(pitfalls) >= 2):
        pitfalls = base['pitfalls']
    out = {
        'creative': str(data.get('creative') or base['creative']).strip(),
        'style_rec': str(data.get('style_rec') or base['style_rec']).strip(),
        'compose': str(data.get('compose') or base['compose']).strip(),
        'palette': {'swatches': list(sw)[:6],
                    'logic': str(pal.get('logic')
                                 or base['palette']['logic']).strip()},
        'highlight': str(data.get('highlight') or base['highlight']).strip(),
        'pitfalls': [str(p).strip() for p in pitfalls[:5]],
        'prompt': str(data.get('prompt') or base['prompt']).strip(),
    }
    # 关键字段全空视为无效
    if not out['creative'] and not out['prompt']:
        return None
    return out
