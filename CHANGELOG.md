## v0.6.0 (2023-11-12)

### Feat

- removed python 3.7 support
- minimize strings and bytes
- minimize int, float, boolean values

### Fix

- fix crash when minimizing raise statements
- minimize nonlocal and global names
- remove the upper dependency bounds
- minimize kw_defaults correctly
- minimize function defaults
- added py.typed
- minimize type comments

### Refactor

- created MinimizeStructure
- created MinimizeBase
- implemented ValueWrapper

## v0.5.0 (2023-10-20)

### Feat

- support for 3.12

### Fix

- fixed various bugs

## v0.4.0 (2023-09-21)

### Feat

- implemented cli
- support for python 3.7 - 3.11
- progress callback for minimize
