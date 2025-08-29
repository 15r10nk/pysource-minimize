## v0.10.0 (2025-08-29)

### Feat

- **3.14**: added support for template-strings

### Fix

- try to minimize Subscript to Name in Store context

## v0.9.0 (2025-07-05)

### Feat

- implemented minimize_all()
- better minimization for ast.AnnAssign
- better minimization for ast.AugAssign
- try to replace every ast.expr with ast.Constant(0)
- replace names with unique_name_N if possible to show where a common name matters

### Refactor

- fixed typos

## v0.8.0 (2025-04-16)

### Feat

- new cli with visual feedback

### Fix

- minimize MatchValue.value
- minimize Raise.exc
- minimize Call.func
- also minimize left side of an assertion
- improved comprehesion minimization
- NamedConstant has been removed in 3.14

### Refactor

- improved pattern minimization

## v0.7.0 (2024-10-09)

### Feat

- added compilable flag

### Fix

- unified handling of type_params
- minimize default_value of type_params

## v0.6.3 (2024-04-23)

### Fix
- Improve error reporting when source cannot be minimized (#16)
- Complete type hints for public API (#15)

## v0.6.2 (2024-03-25)

### Fix

- minimize (yield) to None
- minimization of MatchClass
- minimization of default arguments
- minimize slice correctly

## v0.6.1 (2023-11-29)

### Fix

- minimize every type comment
- **3.8**: support for Index and ExtSlice
- correct minimization of FormattedValue
- ignore code in async inner scopes when we try to minimize a function to its body
- correct minimization of optional nodes

### Refactor

- extracted parse function

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
