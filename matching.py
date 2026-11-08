"""派单五维匹配算法（功能清单第 39 条）。

通关率 30% + 美学均分 25% + 风格标签重合 25% + 接单评价 10% + 学习稳定性 10%
"""
from databaseinit import Course, CourseProgress, Order, Review, SkillTag


def user_level(user):
    """L1-L4：完全通关的阶段数 + 1（L1 = 还没通 L1 之外的第一阶段）。"""
    stages = Course.query.with_entities(Course.stage_id).distinct().all()
    total_stage_ids = sorted({s[0] for s in stages})
    passed_ids = {p[0] for p in CourseProgress.query.filter_by(
        user_id=user.id, status='passed'
    ).with_entities(CourseProgress.course_id).all()}
    level = 1
    for sid in total_stage_ids:
        cids = [c.id for c in Course.query.filter_by(stage_id=sid).all()]
        if cids and all(cid in passed_ids for cid in cids):
            level += 1
    return level


def aesthetic_avg(user):
    rows = CourseProgress.query.filter_by(user_id=user.id).filter(
        CourseProgress.score.isnot(None)).all()
    if not rows:
        return 50.0
    return round(sum(r.score for r in rows) / len(rows), 1)


def style_overlap(user, order):
    mine = {t.tag for t in SkillTag.query.filter_by(user_id=user.id).all()}
    order_tags = set(order.tags or [])
    if not order_tags:
        return 60
    if not mine:
        return 50
    return int(len(mine & order_tags) / len(order_tags) * 100)


def review_avg(user):
    rows = (Order.query.filter_by(taker_id=user.id, status='settled')
            .with_entities(Order.id).all())
    if not rows:
        return 60.0
    ids = [r[0] for r in rows]
    revs = Review.query.filter(Review.order_id.in_(ids)).all()
    if not revs:
        return 60.0
    return round(sum(r.rating * 20 for r in revs) / len(revs), 1)


def stability(user):
    """学习稳定性：已通课程数越多越稳。"""
    passed = CourseProgress.query.filter_by(
        user_id=user.id, status='passed').count()
    total = Course.query.count()
    if total == 0:
        return 50
    return int(passed / total * 100)


def match_score(user, order):
    if user is None:
        return 0
    detail = {
        '通关率': user_level(user),
        '美学均分': aesthetic_avg(user),
        '风格重合': style_overlap(user, order),
        '接单评价': review_avg(user),
        '学习稳定性': stability(user),
    }
    weights = {'通关率': 0.30, '美学均分': 0.25, '风格重合': 0.25,
               '接单评价': 0.10, '学习稳定性': 0.10}
    score = 0
    for k, w in weights.items():
        v = detail[k]
        if k == '通关率':
            v = min(v * 25, 100)
        score += v * w
    return int(round(score)), {k: round(v, 1) for k, v in detail.items()}
