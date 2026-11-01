# Backend architecture

Keep domain apps; introduce named service ownership and explicit transaction boundaries for balances, allocations, reconciliation and jobs. Serializer/view layers validate and authorize; services calculate/mutate; models enforce relational invariants; jobs are idempotent. Compatibility contracts precede extraction.
