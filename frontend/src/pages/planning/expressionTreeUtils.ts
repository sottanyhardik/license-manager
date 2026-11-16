import type { RuleCondition } from '@/api/planningRuleApi';

export const emptyRuleCondition = (): RuleCondition => ({ field: 'HSN', comparator: 'STARTS_WITH', value: '' });
