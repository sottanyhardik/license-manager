import type { RuleCondition } from '@/services/api/planningRuleApi';

export const emptyRuleCondition = (): RuleCondition => ({ field: 'HSN', comparator: 'STARTS_WITH', value: '' });
