# Alpha981 deployment cleanup

Fresh ARIA installations now provision only ARIA and Qdrant. Provider-native web tooling is the supported web-search path.

An upgraded installation may still have old `searxng` or `searxng-valkey` containers and volumes from an earlier stack. Normal ARIA updates deliberately do not stop or delete them. After confirming that the current ARIA stack is healthy and no other application uses those resources, an operator may remove those legacy containers and volumes manually. Keep a backup and verify the exact Compose project before deleting anything.
