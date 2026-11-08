"""填充演示数据（仅本地）：python -X utf8 seed.py

run_seed() 需在 app 上下文中调用，清库重建后灌入演示数据；
开发环境空库时由 databaseinit.init_db 自动调用，生产绝不触发。
"""
from datetime import datetime, timedelta

from databaseinit import (Artwork, Client, Comment, Course, CourseProgress,
                          Favorite, Feedback, Follow, GenLog, Internship, Like,
                          Material, Message, Order, OrderRecord, Partner,
                          RechargeLog, SkillTag, Stage, TeachingEval, User,
                          WorkflowCase, db)
from aesthetics import score_artwork

DEMO_PASSWORD = 'frame123'

PARTNERS = [
    ('院校', '江南大学设计学院', '共建《品牌视觉实训》课程模块，学分置换闯关 L3',
     'grad:linear-gradient(135deg,#80A4D4,#EAF7ED)'),
    ('院校', '中国美术学院创新设计学院', '联合命题「传统纹样再设计」，优秀作品直推主站广场',
     'grad:linear-gradient(135deg,#9FE2EE,#7B75C9)'),
    ('院校', '广州美术学院视觉学院', '学期工作坊：商业插画风格拆解与复刻',
     'grad:linear-gradient(135deg,#E0FAFF,#80A4D4)'),
    ('院校', '同济大学设计创意学院', '新媒体三图联动实战课题联合评审',
     'grad:linear-gradient(135deg,#EAF7ED,#DAE8FB)'),
    ('院校', '四川美术学院', '毕业创作答辩评委直通 L4 终关',
     'grad:linear-gradient(135deg,#7B75C9,#E0FAFF)'),
    ('机构', '站酷高研院', '提供风格语言进阶直播课，闯关 L2 学员享 8 折',
     'grad:linear-gradient(135deg,#6A4DD4,#E2ECF5)'),
    ('机构', '特赞 Tezign', '真实商业命题定期进派单大厅，L3+ 可报名',
     'grad:linear-gradient(135deg,#A4A7E3,#6E3377)'),
    ('机构', '本地设计社群·帧友会', '每月线下作品互评会，教育端素材库共建',
     'grad:linear-gradient(135deg,#75CBD1,#DAE8FB)'),
    ('机构', '悟空图像学院', '提供工具链教程与素材授权，工作流案例共建',
     'grad:linear-gradient(135deg,#F2D2FF,#75CBD1)'),
    ('大厂青苗', '字节跳动 · 青苗计划', '视觉设计青苗实习：参与抖音品牌视觉项目',
     'grad:linear-gradient(135deg,#3E5BA3,#75CBD1)'),
    ('大厂青苗', '腾讯 CDC · 新苗计划', '品牌与交互方向实习转正通道',
     'grad:linear-gradient(135deg,#0C0D45,#A4A7E3)'),
    ('大厂青苗', '小红书设计中心 · 薪火计划', '商业化视觉设计实习，带教导师制',
     'grad:linear-gradient(135deg,#6E3377,#F2D2FF)'),
    ('大厂青苗', '网易 UEDC · 青年引擎', '游戏美术与品牌双方向实习',
     'grad:linear-gradient(135deg,#6A4DD4,#9FE2EE)'),
]

MATERIALS = [
    ('经典艺术', '浮世绘', '神奈川冲浪里', '葛饰北斋', '1831', '海报构图参考',
     'grad:linear-gradient(135deg,#75CBD1,#3E5BA3)',
     {'构图亮点': '大三角波浪压住画面下沿，富士山收在负空间里，视觉张力极强',
      '色彩逻辑': '普鲁士蓝单色系分层，靠明度差拉开远近',
      '视觉层级': '浪-船-山三层递进，视线由动到静',
      '美学韵律': '浪爪的重复排布形成韵律，抓人又不乱',
      '可借鉴点': '用大面积主体+小负空间的做法做活动主视觉'}),
    ('经典艺术', '印象派', '睡莲系列', '莫奈', '1897', '柔和色彩氛围参考',
     'grad:linear-gradient(135deg,#9FE2EE,#80A4D4)',
     {'构图亮点': '水平线消解，水面与倒影无缝衔接，无边界构图',
      '色彩逻辑': '蓝紫邻近色+粉橙点点缀，冷中带暖',
      '视觉层级': '靠笔触密度区分远近，虚化边缘聚焦中心',
      '美学韵律': '笔触的大小疏密形成呼吸感',
      '可借鉴点': '品牌氛围稿可以借用这种无边界水色处理'}),
    ('经典艺术', '构成主义', '红楔子攻打白军', '李西茨基', '1920', '几何海报参考',
     'grad:linear-gradient(135deg,#DAE8FB,#F2D2FF)',
     {'构图亮点': '红楔子以锐角切入白圆，动态对抗一目了然',
      '色彩逻辑': '红白黑三色，极简且冲突强烈',
      '视觉层级': '几何形即信息，无多余装饰',
      '美学韵律': '斜向轴线贯穿，方向感统一',
      '可借鉴点': '促销/对抗主题海报直接套用锐角几何语言'}),
    ('经典艺术', '包豪斯', '包豪斯展览海报', 'Joost Schmidt', '1923', '版式网格参考',
     'grad:linear-gradient(135deg,#E2ECF5,#6A4DD4)',
     {'构图亮点': '网格化的几何模块拼合，信息块对齐严谨',
      '色彩逻辑': '黄红蓝基础色+大面积留白',
      '视觉层级': '模块化分区，阅读顺序由块面引导',
      '美学韵律': '模块间等距间隔形成节奏',
      '可借鉴点': '展览/活动信息版式直接参考其网格结构'}),
    ('现代商业', '扁平商业', 'Spotify 年度 wrapped', 'Spotify 设计团队', '2023', '新媒体视觉参考',
     'grad:linear-gradient(135deg,#6A4DD4,#E2ECF5)',
     {'构图亮点': '超大数字/人像出血排版，冲击力第一',
      '色彩逻辑': '高饱和撞色+深底，屏幕传播效果拉满',
      '视觉层级': '大图-大字-小注三级，几乎零阅读成本',
      '美学韵律': '圆角与有机形状贯穿统一',
      '可借鉴点': '数据可视化海报的出血式大字排版'}),
    ('现代商业', '三维写实', 'Apple 产品渲染', 'Apple 设计团队', '2024', '产品渲染参考',
     'grad:linear-gradient(135deg,#EAF7ED,#9FE2EE)',
     {'构图亮点': '产品居中微仰视，金属质感撑满画面',
      '色彩逻辑': '灰白基底+品牌色点缀，克制',
      '视觉层级': '产品即英雄，文字退居角落',
      '美学韵律': '大面积渐变底形成高级感',
      '可借鉴点': '产品详情页首屏的三维渲染灯光方案'}),
    ('现代商业', '国潮', '故宫文创日历', '故宫文创团队', '2022', '文创产品参考',
     'grad:linear-gradient(135deg,#6E3377,#F2D2FF)',
     {'构图亮点': '传统纹样居中对称，金色描边定视觉中心',
      '色彩逻辑': '朱红+石青+描金，传统色谱现代表达',
      '视觉层级': '纹样-书法-信息三层，井然有序',
      '美学韵律': '连续纹样形成边框韵律',
      '可借鉴点': '文创包装的对称构图+描金工艺语言'}),
    ('现代商业', '酸性设计', 'Acid Graphics 海报', '当代设计工作室', '2023', '潮流海报参考',
     'grad:linear-gradient(135deg,#A4A7E3,#6E3377)',
     {'构图亮点': '金属质感字形+液态形体重叠，制造迷幻空间',
      '色彩逻辑': '荧光绿紫撞色，暗底高亮',
      '视觉层级': '故意打破层级，以噪点纹理统一',
      '美学韵律': '重复的液态金属符号形成迷幻节奏',
      '可借鉴点': '音乐节/潮流活动主视觉的材质混搭'}),
    ('现代商业', '极简', 'MUJI 海报', '原研哉事务所', '2019', '品牌调性参考',
     'grad:linear-gradient(135deg,#EAF7ED,#DAE8FB)',
     {'构图亮点': '地平线构图，人与环境极致留白',
      '色彩逻辑': '大地色+米白，近乎无色',
      '视觉层级': '一行文字一组图，少即是多',
      '美学韵律': '空白与元素的疏密对比即韵律',
      '可借鉴点': '品牌理念类海报的留白哲学'}),
    ('小众创意', '像素', '像素城市计划', '独立设计师社群', '2021', '像素风参考',
     'grad:linear-gradient(135deg,#80A4D4,#EAF7ED)',
     {'构图亮点': '等距像素建筑群，前景后景按色阶推进',
      '色彩逻辑': '有限色板，邻近色阶分层',
      '视觉层级': '像素粒度统一，层级靠色彩',
      '美学韵律': '网格重复自带复古节奏',
      '可借鉴点': '游戏宣发/社群运营插画的像素工作流'}),
    ('小众创意', '涂鸦', '伦敦街头涂鸦', 'Banksy（attrib.）', '2018', '街头潮流参考',
     'grad:linear-gradient(135deg,#0C0D45,#A4A7E3)',
     {'构图亮点': '单色模板喷绘+环境互动，因地制宜',
      '色彩逻辑': '黑白主体+环境色反衬',
      '视觉层级': '一眼看懂的图形语言',
      '美学韵律': '喷绘噪点质感统一',
      '可借鉴点': '用环境互动思维做快闪店与街拍物料'}),
    ('美学理论', '色彩理论', '伊顿色彩球', '约翰内斯·伊顿', '1961', '配色方法论',
     'grad:linear-gradient(135deg,#F2D2FF,#75CBD1)',
     {'构图亮点': '球体展开色谱，秩序感即美感',
      '色彩逻辑': '互补、邻近、三角配色体系全展示',
      '视觉层级': '球体主图+图注，教科书式层级',
      '美学韵律': '色环渐变本身就是韵律',
      '可借鉴点': '做配色方案时直接套用伊顿色彩球逻辑'}),
]

STAGES = [
    ('L1', '审美筑基', '认识构图、色彩、层级三大底层维度，建立看图的基本框架', [
        ('三分钟看懂构图', '练习：给校园随手拍做构图标注，识别三分法/对称/引导线'),
        ('色彩情绪实验室', '练习：同一张海报换成三种配色，说明情绪差异'),
        ('视觉层级排序', '练习：给一张电商详情页标注信息优先级'),
        ('留白的力量', '练习：重排一张塞满元素的社团招新海报'),
    ]),
    ('L2', '风格语言', '掌握主流商业风格的识别与复刻方法', [
        ('扁平风拆解', '练习：临摹一张扁平商业插画并说明其形色规律'),
        ('国潮配色实战', '练习：给家乡特产做一组国潮配色方案'),
        ('三维质感入门', '练习：用渐变与阴影伪造 2.5D 质感'),
        ('酸性风格边界', '练习：为音乐节做一版酸性风格主视觉'),
    ]),
    ('L3', '商业落地', '把审美转成可交付的商业稿件', [
        ('品牌主视觉提案', '练习：为奶茶品牌做一页 KV 提案（含理念阐述）'),
        ('包装版式规范', '练习：为文创产品做包装展开图，标注出血与工艺'),
        ('新媒体三图联动', '练习：一套活动物料产出 KV/详情/头图三张'),
        ('提案叙事训练', '练习：用五页 PPT 讲清你的设计逻辑'),
    ]),
    ('L4', '风格突破', '在成熟规范之上建立个人识别度', [
        ('个人风格试验场', '练习：同一命题产出三种个人化诠释'),
        ('跨媒介迁移', '练习：把平面主视觉迁移到三维或动态'),
        ('系列感构建', '练习：产出 3 件同一世界观的系列作品'),
        ('毕业创作答辩', '练习：完成一份完整的个人作品集导览页'),
    ]),
]

INTERNSHIPS = [
    ('青藤文创设计工作室', '平面设计实习生', '120-160/天', 2, ['国潮', '文创'], False),
    ('光屿新媒体 MCN', '新媒体视觉实习生', '3000/月', 2, ['新媒体', '极简'], True),
    ('木星品牌咨询', '品牌设计助理', '150/天', 3, ['品牌', '三维写实'], False),
    ('像素旅行游戏社', '游戏美术实习生', '4000/月', 4, ['像素', '涂鸦'], True),
]

ORDERS = [
    ('毕业季文创帆布袋图案设计', '文创', 480, 7, ['国潮', '插画'], '为毕业季限定帆布袋设计主图案，国潮倾向，需预留单色印刷版'),
    ('校园音乐节主 KV', '海报', 1500, 10, ['酸性', '潮流'], '户外音乐节主视觉，需要潮流冲击力，可含酸性元素，最终输出含 PSD'),
    ('宠物食品包装焕新', '包装', 3200, 15, ['扁平商业', '插画'], '猫粮品牌包装升级，需要系列感，含 3 个 SKU 差异化'),
    ('社团招新系列海报 3 张', '海报', 600, 5, ['扁平商业'], '动漫社招新，风格活泼统一，三张成系列'),
    ('品牌 IP 形象设计', 'IP', 2600, 14, ['IP', '国潮'], '为茶饮品牌设计 IP 形象，含三视图与表情包 6 个'),
    ('直播间贴片与头图一套', '新媒体', 200, 3, ['新媒体', '极简'], '知识区直播间视觉，简洁专业，次日急单'),
]


def run_seed():
    """清库重建并灌入演示数据。惰性引入 app，兼容 init_db 与直接运行。"""
    from app import app
    with app.app_context():
        db.drop_all()
        db.create_all()

        for row in MATERIALS:
            db.session.add(Material(cat=row[0], style=row[1], title=row[2],
                                    artist=row[3], year=row[4], scene=row[5],
                                    cover=row[6], analysis=row[7]))
        db.session.flush()

        stage_ids = []
        for code, name, desc, courses in STAGES:
            s = Stage(code=code, name=name, desc=desc, order=len(stage_ids) + 1)
            db.session.add(s)
            db.session.flush()
            stage_ids.append(s.id)
            for i, (cname, cbrief) in enumerate(courses):
                # 课程来源渠道轮转：B站/小红书/MOOC教材/商业拆分/平台上传
                channel = ['B站', '小红书', 'MOOC教材', '商业拆分', '平台上传'][
                    (len(stage_ids) * 4 + i) % 5]
                db.session.add(Course(stage_id=s.id, name=cname,
                                      brief=cbrief, channel=channel,
                                      order=i + 1))

        # 演示学生：L1 已通关（带 Token 钱包与近期活跃记录，个人中心演示用）
        stu = User(email='student@demo.framelab', email_verified=True,
                   name='林小帧', school='江南大学',
                   major='视觉传达', grade='大二', role='student',
                   points=42, exposure=120, tokens=68, tier=0,
                   resume={'bio': '国潮与扁平商业方向视觉设计学生，闯关 L2 在读，'
                                  '已交付文创帆布袋商单一件。',
                           'skills': ['国潮', '扁平商业', '插画'],
                           'experience': '接单青藤文创帆布袋图案设计（¥480，'
                                         '好评结算）；校园音乐节海报入围前 10。',
                           'works_url': ''})
        stu.created_at = datetime.utcnow() - timedelta(days=220)
        stu.set_password(DEMO_PASSWORD)
        db.session.add(stu)
        # 演示甲方
        cli_user = User(email='client@demo.framelab', email_verified=True,
                        name='青藤文创', role='client', tokens=20)
        cli_user.set_password(DEMO_PASSWORD)
        db.session.add(cli_user)
        # 演示管理员（后台登录用）
        adm_user = User(email='admin@demo.framelab', email_verified=True,
                        name='帧集管理员', role='teacher', verified=True,
                        is_admin=True, tokens=0)
        adm_user.set_password(DEMO_PASSWORD)
        db.session.add(adm_user)
        db.session.flush()

        client = Client(user_id=cli_user.id, company='青藤文创设计工作室',
                        kind='company', verified=True)
        db.session.add(client)
        db.session.flush()

        for tag in ['国潮', '扁平商业', '插画']:
            db.session.add(SkillTag(user_id=stu.id, tag=tag))

        l1_courses = Course.query.filter_by(stage_id=stage_ids[0]).all()
        for i, c in enumerate(l1_courses):
            res = score_artwork(c.name)
            db.session.add(CourseProgress(
                user_id=stu.id, course_id=c.id, score=res['total'],
                dims=res['dims'], weak=[], status='passed', attempts=1,
                updated_at=datetime.utcnow() - timedelta(days=170 - i * 25)))
        db.session.add(TeachingEval(user_id=stu.id, kind='stage',
                                    title='阶段通关：L1 审美筑基',
                                    detail='全部 %d 关通过' % len(l1_courses)))

        for i, (title, style) in enumerate([('春日招贴', '国潮'),
                                            ('校园之声', '扁平商业'),
                                            ('江城子·文创再设计', '国潮')]):
            db.session.add(Artwork(
                user_id=stu.id, title=title, source='external',
                style_tag=style,
                cover='grad:linear-gradient(135deg,#6A4DD4,#E2ECF5)',
                created_at=datetime.utcnow() - timedelta(days=200 - i * 70)))

        for i, (title, type_, budget, days, tags, req) in enumerate(ORDERS):
            o = Order(client_id=client.id, title=title, type=type_,
                      budget=budget, days=days, tags=tags, requirement=req,
                      deposit=max(round(budget * 0.2, 2), 50))
            db.session.add(o)
            db.session.flush()
            db.session.add(OrderRecord(order_id=o.id, action='publish',
                                       actor_id=cli_user.id,
                                       note='已托管保证金 %.0f 元' % o.deposit))
            if i == 0:
                o.taker_id = stu.id
                o.status = 'accepted'
                db.session.add(OrderRecord(order_id=o.id, action='grab',
                                           actor_id=stu.id, note='接单成功'))

        for company, title, pay, need, tags, remote in INTERNSHIPS:
            db.session.add(Internship(company=company, title=title, pay=pay,
                                      need_level=need, tags=tags, remote=remote))

        db.session.add(WorkflowCase(
            user_id=stu.id, title='国潮文创从 0 到 1 工作流',
            steps=[{'step': '灵感方案', 'content': '主题「江城子」→ 国潮方向，避开同质化的红金套路'},
                   {'step': '提示词', 'content': '石青+月白主色，纹样做 0.618 留白，书法体点题'},
                   {'step': '成稿说明', 'content': '帆布袋/胶带/明信片三件套，单色版已分离'}]))

        # 合作方（教育合作页）
        for kind, name, desc, cover in PARTNERS:
            db.session.add(Partner(kind=kind, name=name, desc=desc,
                                   cover=cover))

        # 钱包与活跃记录（个人中心演示）
        db.session.add(RechargeLog(user_id=stu.id, kind='recharge', tokens=60,
                                  amount=6, note='充值 60 Token',
                                  created_at=datetime.utcnow() - timedelta(days=90)))
        mats_all = Material.query.all()
        db.session.add(Favorite(user_id=stu.id,
                                material_id=mats_all[0].id,
                                folder='构图参考'))
        db.session.add(Favorite(user_id=stu.id,
                                material_id=mats_all[6].id,
                                folder='国潮对标'))
        first_art = Artwork.query.filter_by(user_id=stu.id).first()
        if first_art:
            db.session.add(Like(user_id=cli_user.id,
                                artwork_id=first_art.id))
            db.session.add(Like(user_id=stu.id, artwork_id=first_art.id))
            # 演示评论（作品互动区）
            db.session.add(Comment(user_id=cli_user.id, artwork_id=first_art.id,
                                   content='国潮配色很稳，帆布袋单色版也考虑到了，专业。'))
        # 演示关注关系（甲方 ↔ 学生互关）
        db.session.add(Follow(follower_id=cli_user.id, following_id=stu.id))
        db.session.add(Follow(follower_id=stu.id, following_id=cli_user.id))

        # 更多设计师（风格匹配页演示用）
        extra = [
            ('wang@demo.framelab', '王砚秋', '中国美术学院', '视觉传达', '大三',
             ['国潮', '插画', '品牌'], 3,
             [('敦煌补色计划', '国潮'), ('品牌提案 NO.7', '品牌')]),
            ('chen@demo.framelab', '陈素白', '同济大学', '产品设计', '大二',
             ['极简', '新媒体'], 2,
             [('白噪音·排版实验', '极简'), ('信息流头图组', '新媒体')]),
            ('su@demo.framelab', '苏潮生', '四川美术学院', '数字媒体', '大四',
             ['酸性', '潮流', '像素'], 4,
             [('酸性音乐节主视觉', '酸性'), ('像素旅行·角色组', '像素')]),
        ]
        stage_courses = Course.query.filter_by(stage_id=stage_ids[0]).all()
        for k, (email, name, school, major, grade, tags, lv, works) in enumerate(extra):
            u = User(email=email, email_verified=True, name=name, school=school,
                     major=major, grade=grade, role='student', points=40 + k * 6,
                     exposure=80 + k * 60, tokens=10 + k * 5)
            u.set_password(DEMO_PASSWORD)
            db.session.add(u)
            db.session.flush()
            for t in tags:
                db.session.add(SkillTag(user_id=u.id, tag=t))
            for j, c in enumerate(stage_courses[:lv - 1]):
                res = score_artwork(c.name)
                db.session.add(CourseProgress(
                    user_id=u.id, course_id=c.id, score=res['total'],
                    dims=res['dims'], weak=[], status='passed', attempts=1,
                    updated_at=datetime.utcnow() - timedelta(days=100 - j * 20)))
            for j, (title, style) in enumerate(works):
                db.session.add(Artwork(
                    user_id=u.id, title=title, source='external',
                    style_tag=style,
                    cover='grad:linear-gradient(135deg,#75CBD1,#3E5BA3)',
                    created_at=datetime.utcnow() - timedelta(days=60 - j * 20)))
            # 让高等级设计师有已结算订单，匹配页展示「过往接单评价」
            if lv >= 3:
                o = Order(client_id=client.id, title='%s 主视觉焕新' % name,
                          type='海报', budget=1200, days=10, tags=[tags[0]],
                          requirement='风格匹配演示订单', deposit=240,
                          status='settled', taker_id=u.id)
                db.session.add(o)
                db.session.flush()
                db.session.add(OrderRecord(order_id=o.id, action='publish',
                                           actor_id=cli_user.id, note='已托管保证金'))
                db.session.add(OrderRecord(order_id=o.id, action='grab',
                                           actor_id=u.id, note='接单成功'))
                db.session.add(OrderRecord(order_id=o.id, action='settle',
                                           actor_id=cli_user.id, note='结算完成'))

        # 消息盒子演示（邀约 / 需求通知）
        db.session.add(Message(user_id=stu.id, kind='invite',
                               title='收到来自 青藤文创 的定向邀约',
                               content='看过你的《江城子·文创再设计》，'
                                       '希望合作毕业季系列物料，预算 800-1200。',
                               link='/client/market'))
        db.session.add(Message(user_id=stu.id, kind='order',
                               title='派单大厅有新需求匹配你的风格',
                               content='「品牌 IP 形象设计」与你的标签 国潮 重合度 66%。',
                               link='/client/market', is_read=True))

        # AI 生成历史演示（作品创建页）
        db.session.add(GenLog(user_id=stu.id, prompt='石青月白的国潮帆布袋主图案，'
                              '纹样留白 0.618', style='国潮', model='libai',
                              cover='grad:linear-gradient(135deg,#3E5BA3,#75CBD1)',
                              tokens=3,
                              created_at=datetime.utcnow() - timedelta(days=3)))

        db.session.commit()
        print('seed done: 12 materials, 4 stages 16 courses, 13 partners, '
              'demo student student@demo.framelab/frame123, '
              'demo client client@demo.framelab/frame123, '
              'demo admin admin@demo.framelab/frame123, '
              '6 orders, 4 internships, 3 extra designers, 2 messages, 1 gen log')


def seed():
    run_seed()


if __name__ == '__main__':
    seed()
