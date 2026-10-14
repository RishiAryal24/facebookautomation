from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.entities import RestrictedKeyword, AutomationRule
from app.schemas.schemas import (
    RestrictedKeywordCreate, RestrictedKeywordRead,
    AutomationRuleCreate, AutomationRuleRead
)

router = APIRouter(prefix="/rules", tags=["Automation Rules & Keywords"])

# Restricted Keywords
@router.get("/keywords", response_model=List[RestrictedKeywordRead])
async def list_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(RestrictedKeyword).order_by(RestrictedKeyword.created_at.desc()))
    return result.scalars().all()

@router.post("/keywords", response_model=RestrictedKeywordRead)
async def add_keyword(kw_in: RestrictedKeywordCreate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RestrictedKeyword).where(RestrictedKeyword.keyword == kw_in.keyword))
    if res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Keyword already exists in blacklist")
    
    kw = RestrictedKeyword(
        keyword=kw_in.keyword.strip(),
        category=kw_in.category,
        action=kw_in.action
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw

@router.delete("/keywords/{keyword_id}")
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(RestrictedKeyword).where(RestrictedKeyword.id == keyword_id))
    kw = res.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
    return {"status": "deleted", "id": keyword_id}

# Automation Rules
@router.get("/", response_model=List[AutomationRuleRead])
async def list_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AutomationRule).order_by(AutomationRule.created_at.desc()))
    return result.scalars().all()

@router.post("/", response_model=AutomationRuleRead)
async def create_rule(rule_in: AutomationRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = AutomationRule(
        page_id=rule_in.page_id,
        name=rule_in.name,
        rule_type=rule_in.rule_type,
        trigger_keyword=rule_in.trigger_keyword,
        target_language=rule_in.target_language,
        response_template=rule_in.response_template,
        is_active=rule_in.is_active
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    return {"status": "deleted", "id": rule_id}
