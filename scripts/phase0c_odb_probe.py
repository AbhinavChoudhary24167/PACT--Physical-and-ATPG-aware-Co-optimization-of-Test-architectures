"""Read-only OpenDB interface and port-geometry qualification probe."""
import os
import odb

db = odb.dbDatabase.create()
odb.read_db(db, os.environ["PACT_PHASE0C_PROBE_ODB"])
block = db.getChip().getBlock()
print("dbNet.create", odb.dbNet.create.__doc__)
print("dbBTerm.create", odb.dbBTerm.create.__doc__)
print("dbBPin.create", odb.dbBPin.create.__doc__)
print("dbBox.create", odb.dbBox.create.__doc__)
print("dbBox.destroy", hasattr(odb.dbBox, "destroy"))
print("dbBTerm methods", [x for x in dir(odb.dbBTerm) if x.startswith(('get', 'set'))])
for term in block.getBTerms():
    if term.getName() in ("test_si", "test_so"):
        print("term", term.getName(), term.getIoType(), term.getNet().getName())
        for pin in term.getBPins():
            print("pin", pin.getPlacementStatus(), [(box.getTechLayer().getName(), box.xMin(), box.yMin(), box.xMax(), box.yMax()) for box in pin.getBoxes()])
for term in block.getBTerms():
    for pin in term.getBPins():
        for box in pin.getBoxes():
            if box.xMin() == 0 and 70000 <= box.yMin() <= 100000:
                print("near_left", term.getName(), box.yMin(), box.yMax())
