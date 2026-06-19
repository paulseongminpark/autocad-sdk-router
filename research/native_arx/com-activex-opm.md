# Slice: com-activex-opm

> Coverage-gap fill for the AutoCAD controller's native ARX/DBX plane. Family =
> **COM/ActiveX automation + Object Property Manager (OPM) + the modern AcRxProperty
> system**. Everything below is grounded in ObjectARX 2027 headers and CHMs **read this
> session** from `C:\ObjectARX 2027\inc` (+ the AutoCAD 2027 online/MCP docs noted in
> Sources). Where a fact could not be verified against something read this session it is
> tagged `unverified`.

## Honest tier verdict up front

This family splits into **three tiers of very different value**, and the prompt's framing is
correct:

1. **COM/ActiveX automation object model** (`AcadApplication`/`AcadDocument`/`AcadModelSpace`/
   the `IAcad*` IDispatch tree, `SendCommand`, etc.) — **almost entirely `managed_also` +
   `accoreconsole_lisp_also`, and session-bound.** The ARX side is just an *accessor*:
   `acedGetIDispatch()` (= `AcadGetIDispatch`) hands you AutoCAD's `IDispatch`, and
   `AcApDocument::GetIDispatch()` hands you the document's. Everything reachable through that
   IDispatch is *also* reachable from .NET (`Autodesk.AutoCAD.Interop`) and from LISP
   (`vlax-*`), and **none of it runs under `accoreconsole`** (the COM automation server is the
   full attended `acad.exe` or an out-of-process server). So as a *router capability* this tier
   is low marginal value over the existing managed plane — its only unique pull is driving the
   *live UI session* (palettes, plot dialogs, `SendCommand` to interactive commands).

2. **OPM — exposing properties to the Properties palette / Quick Properties** (the `opm*.h`
   family + `dynprops.h` `IDynamicProperty`/`IPropertyManager`/`IPropertySource`). This is
   **native_arx_only** (C++/ATL/COM authoring of a property provider that AutoCAD's palette
   consumes) and is the *display/edit* surface. It is genuinely native but it is **session-bound
   UI plumbing** — it has no value headless and no value for extraction; its value is "make a
   custom entity's data editable in the palette."

3. **The modern `AcRxProperty` system** (`rxmember.h` / `rxprop.h` / `rxattrib.h` /
   `rxcategory.h` / `rxvalue.h` / `rxvaluetype.h`). **This is the headline and the only part
   that is high-value AND works without the attended UI session.** It is the *introspectable,
   reflective property metamodel* that backs the Properties palette, the .NET property API, data
   extraction, and LMV. A custom entity authored in C++ declares `AcRxProperty` subclasses (with
   `getValue`/`setValue`/`subGetValue`/`subSetValue`), decorates them with `AcRxAttribute`s
   (category, UI placement, units, display-as, COM-name, generate-dynamic-properties…), and from
   then on *any* consumer can enumerate and get/set those properties **generically by name**
   via `AcRxMemberQueryEngine` + `AcRxProperty::getValue` — no per-property C++ switch, no
   DISPID table. **For our controller this is the real prize**: a single generic
   `inspect.entity.properties` / `automate.property.get` op can read every reflected property of
   every entity (built-in and custom) in-process, headless-capable (`objectdbx_capable` for the
   metamodel itself; values that need a live editor are not), and it is the same metadata the
   palette and .NET see. The OPM/COM tiers are essentially the *legacy UI projection* of this
   metamodel.

## Operation catalog

ENGINE_TIER legend: `native_arx_only` | `objectdbx_capable` | `managed_also` |
`accoreconsole_lisp_also`. execution_context legend: `attended_app` (needs full interactive
acad.exe / out-of-process COM server) | `in_proc_arx` (in-process .arx, no UI required) |
`host_dbx` (works in any RealDWG/ObjectDBX host — but note this controller **excludes RealDWG**;
tag means "the API itself is core-2d / dbx-layer, not acad.exe-only").

### Tier 3 — Modern AcRxProperty metamodel (HIGH VALUE, the headline)

| proposed_op_id | native API (class::method) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `extend.property.define` | `AcRxProperty` (subclass; override `subGetValue`/`subSetValue`); ctor `AcRxProperty(const ACHAR* name, const AcRxValueType& type, const AcRxObject* owner=NULL)` | native_arx_only | Declare a single reflected get/set property on a custom AcRxClass. Code, registered at class-registration time. | property name, `AcRxValueType`, owner class | a live `AcRxProperty*` attached to the class's member collection | yes (the *definition* is in the .arx code; the value it exposes persists with the entity if backed by a DWG field) | in_proc_arx | rxprop.h:76-172 (class `AcRxProperty`, `getValue`/`setValue`/`subGetValue`/`subSetValue`) |
| `extend.property.define_collection` | `AcRxCollectionProperty::newValueIterator` / `tryGetCount` (subclass `subNewValueIterator`/`subTryGetCount`) | native_arx_only | Declare a property whose value is an *enumerable collection* (palette shows it as expandable). | property name, type, owner | `AcRxValueIterator*`, count | yes (def in code) | in_proc_arx | rxprop.h:300-395 (`AcRxCollectionProperty`); iterator rxprop.h:242-291 |
| `extend.property.define_indexed` | `AcRxIndexedProperty::getValue/setValue/insertValue/removeValue(pO,int index,…)` | native_arx_only | Declare an index-addressable collection property (get/set/insert/remove by ordinal). | object, index, `AcRxValue` | value / status | yes (def in code) | in_proc_arx | rxprop.h:420-629 |
| `extend.property.define_dictionary` | `AcRxDictionaryProperty::getValue/setValue(pO,const ACHAR* key,…)` | native_arx_only | Declare a key-addressable (string-keyed) collection property. | object, key, `AcRxValue` | value / status | yes (def in code) | in_proc_arx | rxprop.h:639-764 |
| `inspect.entity.properties` | `AcRxMemberQueryEngine::theEngine()->newMemberIterator(pO, ctx)`; iterate `AcRxMemberIterator`; for each `AcRxProperty`, `getValue(pO,value)` | objectdbx_capable | **Generic reflective read of every property of any object** (built-in or custom) by walking the member collection. The core of a generic property-extraction op — no per-class code. | `AcRxObject*` (entity), optional query context | stream of (name, type, value) | n/a (read) | in_proc_arx | rxmember.h:564-624 (`AcRxMemberQueryEngine`, `theEngine`, `newMemberIterator`); get via rxprop.h:95 |
| `inspect.property.by_name` | `AcRxMemberQueryEngine::find(pO, name, ctx)` → cast to `AcRxProperty` → `getValue` | objectdbx_capable | Resolve one property by name on an object and read it, generically. | object, property name | `AcRxValue` | n/a | in_proc_arx | rxmember.h:606 (`find`); rxprop.h:95 |
| `automate.property.set` | `AcRxProperty::setValue(AcRxObject* pO, const AcRxValue& value)` | objectdbx_capable | Generic reflective *write* of a named property value to an object (respects `isReadOnly`). | object, `AcRxValue` | status | yes (if value maps to a persisted field) | in_proc_arx | rxprop.h:112; readonly check rxprop.h:62 |
| `inspect.property.is_readonly` | `AcRxPropertyBase::isReadOnly(const AcRxObject* pO)` | objectdbx_capable | Query whether a property is read-only for a given object instance. | object | bool | n/a | in_proc_arx | rxprop.h:62 |
| `inspect.property.metadata` | `AcRxMember::name/localName/type/attributes/owner/children` | objectdbx_capable | Read a property's static metadata: name, localized name, value type, attribute collection, owner class, child members. | `AcRxMember*` | name, `AcRxValueType&`, `AcRxAttributeCollection&`, owner, children array | n/a | in_proc_arx | rxmember.h:52-112 |
| `extend.property.category` | `AcRxUiPlacementAttribute(const ACHAR* category, unsigned int weight)`; lookup `getCategory`/`getWeight`; tree via `AcRxCategory` | native_arx_only | Place a property under a named UI category with a sort weight (drives palette grouping). | category name, weight | attribute attached; category tree node | yes (def in code) | in_proc_arx | rxattrib.h:302-343 (`AcRxUiPlacementAttribute`); tree rxcategory.h:29-99 (`AcRxCategory`, `rootCategory`, `findDescendant`) |
| `extend.property.describe` | `AcRxDescriptionAttribute(const ACHAR*` or `unsigned int id[,hint])`; `getDescription(pO)` | native_arx_only | Attach a description string (literal or resource-id) shown in the palette. | text or resource id | attribute; resolved `AcString` | yes (def in code) | in_proc_arx | rxattrib.h:372-438 |
| `extend.property.localize_name` | `AcRxLocalizedNameAttribute(id[,sourceHint])` / `AcRxAlternateLocalizedNameAttribute`; `getLocalizedName(pO)` via `AcRxResourceLoader` | native_arx_only | Provide a resource-backed localized member name. | resource id, source hint | localized `AcString` | yes (def in code) | in_proc_arx | rxattrib.h:198-293; loader rxattrib.h:144-196 |
| `extend.property.units` | `AcRxUnitTypeAttribute(UnitType)` (kDistance/kAngle/kArea/kVolume/kCurrency/kPercentage/…) | native_arx_only | Tag a numeric property's unit so the palette formats it correctly. | unit-type enum | attribute | yes (def in code) | in_proc_arx | rxattrib.h:606-645 |
| `extend.property.display_as` | `AcRxDisplayAsAttribute(const ACHAR* name)`; `getDisplayValue(pAttr, AcDbObjectId)` | native_arx_only | Substitute a friendlier display value (e.g. show a referenced object's *name* instead of its ObjectId). | substitute member name; entity id | display `AcString` | yes (def in code) | in_proc_arx | rxattrib.h:482-530 |
| `extend.property.refers_to` | `AcRxRefersToAttribute(const ACHAR* path)`; `parseReference(path,pObject,…)` | native_arx_only | Declare that a property points into a container (e.g. `/LayerTableId/Items`) so the UI can offer pick-from-collection. | container path | resolved `AcRxPropertyBase*` | yes (def in code) | in_proc_arx | rxattrib.h:443-480 |
| `extend.property.flags` | `AcRxFlagsAttribute()` | native_arx_only | Mark a property value as a bitwise flag set (palette renders as checkable flags). | — | attribute | yes (def in code) | in_proc_arx | rxattrib.h:585-603 |
| `extend.property.filepath` | `AcRxFilePathAttribute()` | native_arx_only | Mark a string property as a file path (palette offers a file picker). | — | attribute | yes (def in code) | in_proc_arx | rxattrib.h:565-583 |
| `extend.property.com_name` | `AcRxCOMAttribute(const ACHAR* name)` | native_arx_only + managed_also | Give a member a distinct COM property name (bridges the AcRxProperty member to its equivalent ActiveX property). | COM name | attribute | yes (def in code) | in_proc_arx | rxattrib.h:532-563 |
| `extend.property.expose_to_com` | `AcRxGenerateDynamicPropertiesAttribute()` | native_arx_only → managed_also/attended_app | **Bridge AcRxProperty → COM**: tells AutoCAD to auto-generate `IDynamicProperty2` wrappers for this class/property whenever a COM property inspector examines it (this is the modern way to surface AcRxProperty data into OPM/Properties palette/COM without hand-writing `IDynamicProperty`). | — | attribute; runtime `IDynamicProperty2` wrappers | yes (def in code) | in_proc_arx (effect realized in attended palette) | rxattrib.h:647-665 (doc: "should have IDynamicProperty2 wrappers generated for it whenever it is examined by COM property inspectors") |
| `extend.property.default_value` | `AcRxDefaultValueAttribute(const AcRxValue&)` | native_arx_only | Declare a default value for a property. | `AcRxValue` | attribute | yes (def in code) | in_proc_arx | rxattrib.h:779-786 |
| `extend.property.enum_tag` | `AcRxEnumTag(const ACHAR* name, const AcRxValue& value)`; `value()`/`alternateLocalName()` | native_arx_only | Define an enumeration constant (name↔value) used to render a property as a dropdown. | tag name, value | enum tag member | yes (def in code) | in_proc_arx | rxmember.h:213-269 |
| `extend.property.overrule` | `AcRxPropertyOverrule::getValue/setValue`; register `AcRxMemberOverrule::addOverrule(pMember,pOverrule)` | native_arx_only | Runtime-modify an *existing* property's get/set behavior (incl. built-in entity properties) without subclassing the entity. | target `AcRxProperty`, overrule object | overruled behavior | no | in_proc_arx | rxprop.h:182-216 (`AcRxPropertyOverrule`); rxmember.h:707-760 (`AcRxMemberOverrule::addOverrule/removeOverrule`) |
| `inspect.value.to_string` | `AcRxValueType::toString(instance, buffer, size, StringFormat)` | objectdbx_capable | Convert an `AcRxValue` to its string representation (for extraction / display). | value instance, format | formatted string | n/a | in_proc_arx | rxvaluetype.h:178-338 (`AcRxValueType`, `toString`) |
| `extend.members.facet_provider` | `AcRxFacetProvider::getFacets`; register via `AcRxMemberQueryEngine::addFacetProvider` | native_arx_only | Contribute *additional* members for a class in a given context (dynamic, context-sensitive property sets). | provider object | extra members surfaced by the query engine | no | in_proc_arx | rxmember.h:495-532 (`AcRxFacetProvider`); register rxmember.h:662 |
| `inspect.members.promoted` | `AcRxMemberQueryEngine::promotingContext()` / `AcRxPromotingQueryContext` | objectdbx_capable | Query members with child sub-properties *promoted* to the same level (e.g. StartPoint → Start X / Y / Z). | object | flattened member iterator | n/a | in_proc_arx | rxmember.h:637-650; rxprop.h:218-232 |

### Tier 2 — OPM (Object Property Manager): custom-entity properties in the Properties palette

> All `native_arx_only` and all `attended_app` (the Properties palette / Quick Properties only
> exist in interactive AutoCAD; none of this is reachable under accoreconsole). This is the
> *classic* (pre-AcRxProperty) path and the COM-projection path.

| proposed_op_id | native API (class::method) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `extend.opm.register_provider` | `AcRxDynPropManager` (instantiate in `kInitAppMsg`, delete in `kUnloadAppMsg`); `OPM_DYNPROP_OBJECT_ENTRY_AUTO(CMyDynProp, AcDbLine)` | native_arx_only | Register an OPM dynamic-property provider class against an AcDbClass (or AcDbDatabase for zero-selection, or a command). Walks the `OPM_DYNPROP$` link section and calls `IPropertyManager::AddProperty`. | provider class, target AcRxClass/command | properties attached to the palette for that class | no (provider is code) | attended_app | dynpropmgr.h:12-101 (macros), 105-203 (`AcRxDynPropManager` ctor/dtor: `GET_OPMPROPERTY_MANAGER`, `AddProperty`) |
| `extend.opm.define_property` | implement `IDynamicProperty` (`GetGUID`,`GetDisplayName`,`GetCurrentValueType`,`GetCurrentValueData(objectID,…)`,`SetCurrentValueData`,`IsPropertyEnabled`,`IsPropertyReadOnly`,`GetDescription`,`Connect`/`Disconnect`) | native_arx_only | Author one palette property as a COM object: name/GUID/type + get/set by `objectID` (LONG_PTR) + read-only/enabled + change notification. | DISPID-less COM impl | a palette row | no | attended_app | dynprops.h:252-307 (`IDynamicProperty`, IID 8B384028-ACA9) |
| `extend.opm.define_property2` | implement `IDynamicProperty2` (same as above but `GetCurrentValueData(IUnknown* pUnk,…)` / `SetCurrentValueData(IUnknown*,…)`, `Connect(IDynamicPropertyNotify2*)`) | native_arx_only | The modern OPM property interface keyed on the object's `IUnknown` instead of a LONG_PTR objectID. This is what `AcRxGenerateDynamicPropertiesAttribute` auto-generates. | COM impl | a palette row | no | attended_app | dynprops.h:309-364 (`IDynamicProperty2`, IID 9CAF41C2-CA86-4FFB) |
| `extend.opm.enum_property` | implement `IDynamicEnumProperty` (`GetNumPropertyValues`,`GetPropValueName(index,…)`,`GetPropValueData(index,…)`) | native_arx_only | Render a property as a finite dropdown (enum / value-set). | index queries | dropdown list | no | attended_app | dynprops.h:392-425 (`IDynamicEnumProperty`, IID 8B384028-ACB1) |
| `extend.opm.dialog_property` | implement `IDynamicDialogProperty` (`GetCustomDialogProc(OPMDIALOGPROC*)` or `GetMacroName(BSTR*)`); or `IOPMPropertyDialog::DoModal(BSTR* val, AcDbObjectIdArray*)` | native_arx_only | Give a property an ellipsis (`…`) button that pops a custom dialog or runs a VBA macro to edit the value. | dialog proc / macro name / objectId array | edited value string | no | attended_app | dynprops.h:427-452 (`IDynamicDialogProperty`); opmdialog.h:19-53 (`IOPMPropertyDialog`/`IOPMPropertyDialog2`, IID 8B384029-ACB0 / 9F82F13D) |
| `extend.opm.get_dispid` | implement `IDynamicPropertyGetDispId::GetDispId(DISPID*)` (magic `DISPID_DYNAMIC = -23`) | native_arx_only | Supply a stable DISPID for a dynamic property (so it can be addressed like a static one). | — | DISPID | no | attended_app | dynprops.h:366-390 |
| `extend.opm.property_extension` | `IOPMPropertyExtension::GetDisplayName/Editable/ShowProperty(DISPID,…)` | native_arx_only | Override display name / editability / visibility of *existing* (static) properties in the palette, per DISPID. | DISPID | name / editable / show flags | no | attended_app | opmext.h:31-56 (`IOPMPropertyExtension`, IID 1236EAA4-7715) |
| `extend.opm.property_expander` | `IOPMPropertyExpander`/`IOPMPropertyExpander2::GetElementValue/SetElementValue/GetElementStrings/GetElementGrouping/GetGroupCount` (helper `IOPMPropertyExpanderImpl<T>`) | native_arx_only | Expand a composite/variant property into editable sub-elements (e.g. X/Y/Z of a point) with WCS↔UCS handling. | DISPID, cookie, VARIANT | element values + grouping | no | attended_app | opmext.h:59-141 (`IOPMPropertyExpander`/`2`, IID 5D535710 / D0F45FEB); template opmtempl.h:21-244 (`IOPMPropertyExpanderImpl`) |
| `extend.opm.property_expression` | `IOPMPropertyExpanderExpression::ExpressionAllowed/put_Expression/get_Expression` | native_arx_only | Allow field/parametric *expressions* on an expandable property element. | DISPID, cookie | expression BSTR / allowed flag | no | attended_app | opmext.h:143-171 (IID 4197114D-3CC4) |
| `extend.opm.map_category` | `AcOpmMapPropertyToCategory` / `AcOpmGetCategoryName` / `AcOpmGetParentCategory` / `AcOpmGetCategoryWeight` (ICategorizeProperties driver helpers) + `ACAD_OPMPROPMAP_ENTRY` map | native_arx_only | Map static-property DISPIDs to palette categories, names, parent/weight (the legacy category system; modern equivalent is `AcRxCategory` + `AcRxUiPlacementAttribute`). | DISPID, property map, resources | PROPCAT, category name BSTR | no | attended_app | opmdrvr.h:15-44 (driver fns); map struct opmimp.h:29-72 (`ACAD_OPMPROPMAP_ENTRY`) |
| `extend.opm.per_instance_source` | `IPropertySource` (`get_Name`, `GetDynamicProperty…`) registered via `OPM_DYNPROP_PERINSTANCE_ENTRY_AUTO`; `OPMPerInstancePropertySources::SetPropertySourceAt/GetPropertySourceAt` | native_arx_only | Attach *per-instance* (not per-class) dynamic properties — different palette rows for different instances of the same class. | property source name, source object | per-instance palette rows | no | attended_app | dynprops.h:523-528 + 38-105 (`IPropertySource` IID 61D0A8E3; `OPMPerInstancePropertySources`/`…Extension`/`…Factory`) |
| `extend.opm.get_manager` | `GET_OPMPROPERTY_MANAGER(pAcRxClass)` → `OPMPropertyExtensionFactory::CreateOPMObjectProtocol(pClass)->GetPropertyManager()`; `IPropertyManager::AddProperty/RemoveProperty/GetDynamicProperty/GetDynamicPropertyByName/GetDynamicPropertyCount` | native_arx_only | Get/enumerate/mutate the OPM property manager for a class (the registry the palette reads). | AcRxClass | `IPropertyManager*`; property count/array | no | attended_app | dynprops.h:139-198 (factory + macros), 454-521 (`IPropertyManager`/`IPropertyManager2`, IID 8B384028-ACA9 / FABC1C70) |

### Tier 1 — COM/ActiveX automation object model + ARX↔COM bridging (session-bound, mostly managed_also)

| proposed_op_id | native API (class::method) | engine_tier | what it does | key inputs | key outputs | dwg_persisted? | execution_context | citation |
|---|---|---|---|---|---|---|---|---|
| `automate.com.get_app` | `acedGetIDispatch(bool bAddRef)` (= `AcadGetIDispatch`) | managed_also + accoreconsole_lisp_also | Get AutoCAD's `IDispatch` (the `AcadApplication` automation root) from inside ARX — the entry to the whole `IAcad*` tree (`Documents`, `ActiveDocument`, `ModelSpace`, `PaperSpace`, `Preferences`…). | bAddRef | `IDispatch*` (AcadApplication) | n/a | attended_app | aced.h:822-824 ("AutoCAD's IDispatch pointer") |
| `automate.com.get_document` | `AcApDocument::GetIDispatch(bool bAddRef)` | managed_also | Get the `AcadDocument` `IDispatch` for a given ARX document (bridges `AcApDocument*` → COM document). | bAddRef | `IDispatch*` (AcadDocument) | n/a | attended_app | acdocman.h:145 |
| `automate.com.get_for_command` | `acedGetIUnknownForCurrentCommand(LPUNKNOWN& pUnk)` | native_arx_only | Get the `IUnknown` associated with the currently executing command (COM context for command-scoped property providers). | — | `IUnknown*` | n/a | attended_app | rxmfcapi.h:177 |
| `automate.com.get_winapp` | `acedGetAcadWinApp()` → `CWinApp*` | native_arx_only | Get AutoCAD's MFC `CWinApp` (host window/app object; rarely needed for automation, but the MFC bridge). | — | `CWinApp*` | n/a | attended_app | rxmfcapi.h:58-61 |
| `automate.com.send_command` | (no native export found this session) — via COM: `AcadDocument::SendCommand(BSTR)` obtained from `automate.com.get_document` | managed_also + accoreconsole_lisp_also | Send a command string to the live document command line. **No ARX C++ export exists in the headers searched**; reachable only through the COM IDispatch (or `acedCommand`/`acedCommandS` on the ARX side, which is a *different* native API, not COM). | command string | execution | side-effects | attended_app | `unverified` — grep of axtempl.h/axtypes.idl found no `SendCommand`/`PostCommand`; the method lives in the type library `acax26ENU.tlb` (inc-x64), not in a readable .h this session |
| `automate.com.bridge_objectid` | `acdbGetObjectId(AcDbObjectId&, const ads_name)` / `acdbGetAdsName(ads_name&, AcDbObjectId)` | objectdbx_capable + accoreconsole_lisp_also | Translate between `AcDbObjectId` and `ads_name` — the handle the COM/automation layer and AutoLISP both use to name entities. The canonical ObjectId↔external-name bridge. | ObjectId or ads_name | the other form | n/a | in_proc_arx | dbmain.h:179-181 |
| `automate.com.objectid_from_iunknown` | `IAcadBaseObject::GetObjectId(AcDbObjectId*)` (queried from a COM wrapper's IUnknown) | native_arx_only | Recover the underlying `AcDbObjectId` from a COM entity wrapper (the inverse bridge used throughout OPM templates). | COM wrapper `IUnknown` | `AcDbObjectId` | n/a | attended_app | opmtempl.h:44-51,78-85 (`QueryInterface(IID_IAcadBaseObject)` → `GetObjectId`) |
| `automate.com.wrapper_for_object` | `AcAxGetOleLinkManager()` → `AcAxOleLinkManager::GetIUnknown(AcDbObject*)` / `GetIUnknown(AcDbDatabase*)` / `GetDocIDispatch(AcDbDatabase*)` / `SetIUnknown(...)` | native_arx_only | The ARX↔COM wrapper registry: given a DB-resident object/database, get (or set) its COM wrapper `IUnknown`, or the owning document's `IDispatch`. The authoritative `AcDbObject ↔ IAcad*` mapping. | `AcDbObject*` / `AcDbDatabase*` (+ optional `AcDbSubentId`) | `IUnknown*` / `IDispatch*` | n/a | attended_app | oleaprot.h:23-67 (`AcAxOleLinkManager`, `AcAxGetOleLinkManager`) |
| `automate.com.hold_objectref` | `AcAxObjectRef` (`acquire`/`release`/`objectId`/`isNull`) + smart ptr `AcAxObjectRefPtr<T>` | native_arx_only | Hold a reference to an `AcDbObject` *as either an ObjectId or a pointer* across a COM call boundary, without the caller knowing which — the standard COM-wrapper backing store. | ObjectId or `AcDbObject*` | managed open/close of the object | n/a | in_proc_arx | axobjref.h:61-297 |
| `automate.com.lock_document` | `AcAxDocLock` (ctor locks; `lockStatus()`; `document()`; `DocLockType{kNormal,kCurDocSwitch}`) | native_arx_only | RAII document lock required before any COM/automation *write* to a database from session context (also switches doc context with `kCurDocSwitch`). Without it, appends from a COM client fail. | ObjectId / AcDbDatabase / current doc | lock + status | n/a | attended_app | axlock.h:22-77 (`AcAxDocLock`) |
| `automate.com.entity_helpers` | `axboiler.h` `AcAx*` library: `AcAxRotate`, `AcAxMirror`, `AcAxScaleEntity`, `AcAxTransformBy`, `AcAxArrayPolar`, `AcAxArrayRectangular`, `AcAxGetBoundingBox`, `AcAxIntersectWith`, `AcAxGet/PutColor`, `AcAxGet/PutLayer`, `AcAxGet/SetXData`, `AcAxGetHandle`, `AcAxHighlight`, … (all take `AcAxObjectRef&`/`AcDbObjectId` + `VARIANT`/`LPDISPATCH`) | native_arx_only + managed_also | Ready-made C++ helpers implementing the *body* of the ActiveX entity methods (the boilerplate behind `IAcadEntity`): geometric ops, common-property get/put, XData, bounding box, array — operating on an `AcAxObjectRef` with VARIANT args. Useful if we author our own COM wrappers. | `AcAxObjectRef&` + VARIANTs | per-method (status / geometry / property) | varies (geometry/XData persist) | attended_app | axboiler.h:279,340,406,464 + section index (AcAxRotate/Mirror/ArrayPolar/GetXData/GetBoundingBox/IntersectWith/Get/Put*…) |
| `embed.ole.frame` | `AcDbOle2Frame` (`setOleClientItem(COleClientItem*)` / `getOleClientItem`, `setLocation`/`getLocation`, `position`/`setPosition`, `getType`(link/embed/static), `getLinkName`/`getLinkPath`/`isLinked`, `rotation`/`setRotation`, `wcsWidth`/`wcsHeight`, `scaleWidth`/`scaleHeight`, `lockAspect`, `outputQuality`) | native_arx_only (subGetClassID makes it objectdbx_capable for I/O) | Create/inspect an **embedded or linked OLE object as a real DWG entity** (the OLEFRAME). Set its source MFC `COleClientItem`, place/scale/rotate it, read its link target and type. The OLE COM wrapper class ID comes from `subGetClassID`. | `COleClientItem*`, geometry | a persisted `AcDbOle2Frame` entity | **yes** (OLE frames persist in the DWG) | attended_app (creating/activating needs MFC/OLE host) | dbole.h:49-219 (`AcDbOleFrame`/`AcDbOle2Frame`) |

## Classes & subsystems covered

- **Modern property metamodel** (`rxmember.h`, `rxprop.h`): `AcRxMember`, `AcRxMemberCollection`,
  `AcRxMemberCollectionBuilder`, `AcRxMemberIterator`, `AcRxMemberQueryContext`,
  `AcRxMemberQueryEngine`, `AcRxFacetProvider`, `AcRxMemberReactor`, `AcRxMemberOverrule`,
  `AcRxEnumTag`; `AcRxPropertyBase`, `AcRxProperty`, `AcRxPropertyOverrule`,
  `AcRxCollectionProperty`(+Overrule), `AcRxIndexedProperty`, `AcRxDictionaryProperty`,
  `AcRxValueIterator`, `AcRxPromotingQueryContext`.
- **Property attributes** (`rxattrib.h`): `AcRxAttribute`, `AcRxAttributeCollection`,
  `AcRxResourceLoader`, `AcRxLocalizedNameAttribute`, `AcRxAlternateLocalizedNameAttribute`,
  `AcRxUiPlacementAttribute`, `AcRxLMVAttribute`, `AcRxDescriptionAttribute`,
  `AcRxRefersToAttribute`, `AcRxDisplayAsAttribute`, `AcRxCOMAttribute`, `AcRxFilePathAttribute`,
  `AcRxFlagsAttribute`, `AcRxUnitTypeAttribute`, `AcRxGenerateDynamicPropertiesAttribute`,
  `AcRxUseDialogForReferredCollectionAttribute`, `AcRxUiCascadingContextMenuAttribute`,
  `AcRxCumulativeAttribute`, `AcRxAffinityAttribute`, `AcRxTypePromotionAttribute`,
  `AcRxDefaultValueAttribute`.
- **Categories** (`rxcategory.h`): `AcRxCategory` (tree: `rootCategory`, `findDescendant`,
  `removeChild`), `acdbGet/SetLegacyCategoryId`. (`AcRxCategoryAttribute` is referenced by
  rxcategory.h's doc comment as the attribute that names a category from a property — the named
  attribute class itself was not found as a distinct declaration in the headers read this
  session; `unverified` whether it is its own class vs. realized through `AcRxUiPlacementAttribute`.)
- **Value system** (`rxvalue.h`, `rxvaluetype.h`): `AcRxValue`, `AcRxBoxedValue`,
  `AcRxBoxedValueOnStack`, `AcRxValueType` (`toString`, `StringFormat`). (Read at the
  class/decl level this session; individual value accessors not exhaustively enumerated —
  flagged where a value op cites them.)
- **OPM dynamic properties** (`dynprops.h`): `IDynamicProperty`, `IDynamicProperty2`,
  `IDynamicEnumProperty`, `IDynamicDialogProperty`, `IDynamicPropertyGetDispId`,
  `IDynamicPropertyNotify`/`Notify2`, `IPropertyManager`, `IPropertyManager2`, `IPropertySource`,
  `OPMPropertyExtension`, `OPMPropertyExtensionFactory`, `OPMPerInstancePropertySources`,
  `OPMPerInstancePropertyExtension`, `OPMPerInstancePropertyExtensionFactory`; the
  `GET_OPM*` access macros.
- **OPM extension/driver/template** (`opmext.h`, `opmdrvr.h`, `opmimp.h`, `opmtempl.h`,
  `opmdialog.h`): `IOPMPropertyExtension`, `IOPMPropertyExpander`/`2`,
  `IOPMPropertyExpanderExpression`, `IOPMPropertyDialog`/`2`, the `AcOpm*` ICategorizeProperties/
  IPerPropertyBrowsing/IAcPi* driver functions, `ACAD_OPMPROPMAP_ENTRY`, `IOPMPropertyExpanderImpl<T>`.
- **OPM registration** (`dynpropmgr.h`): `AcRxDynPropManager`, `OPM_DYNPROP_OBJECT_ENTRY_AUTO`,
  `OPM_DYNPROP_COMMAND_ENTRY_AUTO`, `OPM_DYNPROP_PERINSTANCE_ENTRY_AUTO`,
  `OPM_DYNPROP_OBJECT_LEGACY1ENTRY_AUTO`, the `OPM_DYNPROP$` link sections.
- **COM/ActiveX bridging** (`aced.h`, `acdocman.h`, `rxmfcapi.h`, `oleaprot.h`, `axlock.h`,
  `axobjref.h`, `axboiler.h`, `dbmain.h`): `acedGetIDispatch`/`AcadGetIDispatch`,
  `AcApDocument::GetIDispatch`, `acedGetIUnknownForCurrentCommand`, `acedGetAcadWinApp`,
  `AcAxOleLinkManager`+`AcAxGetOleLinkManager`, `AcAxDocLock`, `AcAxObjectRef`/`AcAxObjectRefPtr`,
  the `AcAx*` helper library, `acdbGetObjectId`/`acdbGetAdsName`, `IAcadBaseObject::GetObjectId`.
- **OLE embedding** (`dbole.h`): `AcDbOleFrame`, `AcDbOle2Frame`.
- **DISPIDs** (`axdispids.h`): standard entity property DISPIDs (`DISPID_ACADCOLOR=0x500`,
  `…LAYER=0x501`, `…LINETYPE`, `…LINETYPESCALE`, `…PLOTSTYLENAME=0x513`, `…LINEWEIGHT=0x514`,
  `…HYPERLINKS`, `…MATERIAL=0x577`, `…VISUALSTYLE=0x578`).

## Build / integration notes

- **Libs / SDK**: link from `C:\ObjectARX 2027\lib-x64`. The modern AcRxProperty + attributes
  live in **`ac*base`/`acdbcore2d`** (port macros `ACBASE_PORT`, `ACDBCORE2D_PORT`) — i.e. the
  *core* layer, which is why the metamodel is `objectdbx_capable`, not acad.exe-bound. OPM/COM
  symbols (`AXAUTOEXP`, the `dynprops.h`/`opm*.h` interfaces) come from the automation/OPM libs
  and **only resolve inside attended AutoCAD** (the palette host).
- **COM type library**: the readable `IAcad*` automation surface (incl. `SendCommand`,
  `PostCommand`, `ModelSpace.AddLine`, etc.) is NOT in a `.h` — it is the type library
  `acax26ENU.tlb` / `axdb26enu.tlb` in `inc-x64`, consumed via `#import` or `axdb.h`
  (`AcAxDb26res.dll`). Any op that drives those methods must `#import` the TLB; that is why
  Tier-1 automation ops are tagged `managed_also` (the .NET interop assemblies wrap the same TLB)
  and why the only *native, header-grounded* Tier-1 ops are the **bridges/accessors**, not the
  automation verbs themselves.
- **accoreconsole reality**: `accoreconsole.exe` (the headless host this controller already uses
  for `dwg_truth_autocad`) **does not host the COM automation server and does not host the
  Properties palette.** Therefore: Tier-2 (OPM) and the `attended_app` Tier-1/Tier-3 ops are
  *only* reachable in a full interactive `acad.exe` session (or an out-of-process COM server we
  spawn). The `objectdbx_capable` AcRxProperty *read/write* ops (`inspect.entity.properties`,
  `inspect.property.by_name`, `automate.property.set`, value/metadata) run **in-process in any
  ARX/core host** — including, in principle, headless core hosts — because the metamodel is core,
  not UI.
- **Authoring a custom-entity property surface (recommended path)**: define `AcRxProperty`
  subclasses on the entity's `AcRxClass` (via `ACRX_DECLARE_MEMBERS`/member registration),
  decorate with `AcRx*Attribute`s, and attach **`AcRxGenerateDynamicPropertiesAttribute`** —
  AutoCAD then auto-bridges them to `IDynamicProperty2` for the palette/COM. This *replaces*
  hand-writing `IDynamicProperty` + `AcRxDynPropManager` for new work; the OPM `IDynamicProperty`
  path remains for legacy/per-instance/expander/ellipsis-dialog cases.
- **Document locking is mandatory** for COM-context writes: wrap any append/modify reached
  through the automation/COM layer in `AcAxDocLock` (`kCurDocSwitch` if switching doc context).
- **VS2026 C++ toolset** + the ATL headers (the OPM templates pull `CComPtr`, `CComBSTR`,
  `ATLASSERT`, `_com_util`, `__uuidof`) — OPM/COM code needs ATL; the pure AcRxProperty
  metamodel does not.

## C++-only delta (esp. AcRxProperty + OPM vs managed)

- **AcRxProperty metamodel — authoring is C++-only; reading is partially shared.** *Declaring*
  new reflected properties on a custom entity (`AcRxProperty`/`AcRxCollectionProperty`/
  `AcRxIndexedProperty`/`AcRxDictionaryProperty` subclasses + attribute decoration + facet
  providers + overrules) is **native_arx_only** — there is no managed API to *add* an
  `AcRxProperty` to a native class's member set, and LISP/accoreconsole cannot author it at all.
  *Consuming* it (enumerate members, get/set by name) is exposed to .NET as well
  (`Autodesk.AutoCAD.DatabaseServices`/the property pipeline), so a generic *reader* op is
  `objectdbx_capable`/`managed_also`; but the C++ path is the only one that is fully in-process,
  zero-marshaling, and can drive `subGetValue`/`subSetValue`/overrules/facets. **This is the part
  of the family with real native-only leverage and it is high value** (one generic op reads/writes
  every reflected property of every entity).
- **OPM (`IDynamicProperty*` / `IPropertyManager` / `IPropertySource` / `IOPMProperty*`) is
  C++/ATL/COM-only authoring**, but it is **UI plumbing**: its sole effect is rows in the
  Properties palette / Quick Properties of an attended session. Managed .NET *can* implement OPM
  via `Autodesk.AutoCAD.Runtime`/`IDynamicProperty` COM interop, so this is not strictly
  C++-only — but the native ATL path (`AcRxDynPropManager` + the `OPM_DYNPROP$` link section) is
  the canonical one. **Low marginal value for a router** unless we specifically need to surface
  data into the interactive palette.
- **COM automation object model is the opposite of a C++ delta** — it is the *lowest* native
  leverage of the three. The `IAcad*` verbs are TLB-defined and equally (more conveniently)
  driven from .NET and LISP; ARX's only unique contribution is the *bridges*
  (`acedGetIDispatch`, `AcAxOleLinkManager`, `acdbGetObjectId`, `AcAxObjectRef`, `AcAxDocLock`)
  and the `AcAx*` helper bodies. All of it is `attended_app` / session-bound. **A controller that
  already has a managed plane gains little by re-exposing COM automation natively** — the honest
  recommendation is to reach the automation object model from the existing managed/`CadJobRunner`
  plane (or LISP under accoreconsole for the non-COM subset), and reserve native C++ here for
  (a) the AcRxProperty metamodel and (b) `AcDbOle2Frame` OLE embedding.
- **OLE embedding (`AcDbOle2Frame`) is genuinely native and persists in the DWG** — it is the one
  Tier-1 op that produces durable geometry and has no clean managed equivalent for full control
  (managed exposes a limited OLE wrapper). Worth a native op if embedding OLE content is a goal.

## Sources actually read (this session)

Local ObjectARX 2027 headers (`C:\ObjectARX 2027\inc`), read in full or programmatically
extracted this session:

- `rxmember.h` (full, 761 lines) — AcRxMember / query engine / overrule / enum tag.
- `rxprop.h` (full, 765 lines) — AcRxProperty family.
- `rxattrib.h` (full, 787 lines) — all property attributes.
- `rxcategory.h` (full, 99 lines) — AcRxCategory.
- `dynprops.h` (lines 1-528 read; 780 total) — IDynamicProperty/2, IPropertyManager/2,
  IPropertySource, enum/dialog/getdispid/notify interfaces, OPM extension/per-instance classes +
  GET_OPM* macros (with IID GUIDs).
- `dynpropmgr.h` (full, 204 lines) — AcRxDynPropManager + OPM_DYNPROP macros.
- `opmext.h` (full, 176 lines) — IOPMPropertyExtension / Expander / ExpanderExpression (+ GUIDs).
- `opmdrvr.h` (full, 47 lines) — AcOpm* driver functions.
- `opmdialog.h` (full, 56 lines) — IOPMPropertyDialog / 2 (+ GUIDs).
- `opmtempl.h` (full, 245 lines) — IOPMPropertyExpanderImpl<T> ATL template.
- `opmimp.h` (extracted) — ACAD_OPMPROPMAP_ENTRY map + entry-builder macros.
- `opmexp.h` (lines 1-130 read + extracted) — COM element get/set macros (WCS/UCS bridging).
- `axlock.h` (full, 82 lines) — AcAxDocLock.
- `axobjref.h` (full, 298 lines) — AcAxObjectRef / AcAxObjectRefPtr.
- `oleaprot.h` (full, 73 lines) — AcAxOleLinkManager + AcAxGetOleLinkManager.
- `dbole.h` (full, 224 lines) — AcDbOleFrame / AcDbOle2Frame.
- `axboiler.h` (extracted — section index + key AcAx* helper signatures).
- `axdispids.h` (full, 22 lines) — standard entity DISPIDs.
- `aced.h` (lines 821-826) — acedGetIDispatch / AcadGetIDispatch.
- `acdocman.h` (line 145, grep) — AcApDocument::GetIDispatch.
- `rxmfcapi.h` (lines 58-61,177, grep) — acedGetAcadWinApp / acedGetIUnknownForCurrentCommand.
- `dbmain.h` (lines 170-191) — acdbGetObjectId / acdbGetAdsName.
- `rxvalue.h` / `rxvaluetype.h` (grep + class/decl extraction) — AcRxValue / AcRxValueType /
  toString.
- Header inventory of `C:\ObjectARX 2027\inc` (ax*, opm*, rx*property/attrib/value), `inc-x64`
  (acax26ENU.tlb, axdb.h, axdb26enu.tlb), and `C:\ObjectARX 2027\samples` tree (com/, entity/
  polysamp + compoly ATL COM-wrapper sample, dotNet/).

Autodesk online docs (via `mcp__autodesk-product-help__search_help_content`, ACD/2027):

- "About ObjectARX Applications" — help.autodesk.com/cloudhelp/2027/ENU/AutoCAD-Customization/
  files/GUID-3FF72BD0-9863-4739-8A45-B14AF1B67B06.htm — cited for the cross-API interop
  statement ("use ObjectARX libraries in conjunction with … AutoLISP, ActiveX, or Managed .NET …
  ActiveX and Managed .NET are supported on Windows only").
- "About Specifying Properties for Dynamic Blocks" — GUID-2AD97498-3E30-46E7-A4B3-3AB469C1371A —
  context for Properties-palette custom properties.
- Note: the OARX 2027 Reference (`help.autodesk.com/view/OARX/2027/...`) GUID pages are
  JavaScript SPA shells and the MCP help corpus does **not** index the ObjectARX class reference
  at API granularity (a targeted AcRxProperty/OPM query returned only Vault/SFDC support noise +
  the two customization pages above). Exact C++ signatures in this catalog therefore come from
  the **local headers**, which are the authoritative source; the online Reference would only
  restate them.
