#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Data stores, data sets and data sources
"""

# Data sources
# ============
#
# Should implement:
# * fields
# * prepare()
# * rows() - returns iterable with value tuples
# * records() - returns iterable with dictionaries of key-value pairs
#
# Data targets
# ============
# Should implement:
# * fields
# * prepare()
# * append(object) - appends object as row or record depending whether it is a dictionary or a list
# Optional (for performance):
# * append_row(row) - row is tuple of values, raises exception if there are more values than fields
# * append_record(record) - record is a dictionary, raises exception if dict key is not in field list

import urllib2
import urlparse
import brewery.dq
from brewery.metadata import Field
from brewery.common import collapse_record


class DataStream(object):
    """Shared methods for data targets and data sources"""

    def __init__(self):
        """
        A data stream object – abstract class.

        The subclasses should provide:

        * `fields`

        `fields` are :class:`FieldList` objects representing fields passed
        through the receiving stream - either read from data source
        (:meth:`DataSource.rows`) or written to data target
        (:meth:`DataTarget.append`).

        Subclasses should populate the `fields` property (or implenet an
        accessor).

        The subclasses might override:

        * `initialize()`
        * `finalize()`

        The class supports context management, for example::

            with ds.CSVDataSource("output.csv") as s:
                for row in s.rows():
                    print row

        In this case, the initialize() and finalize() methods are called
        automatically.
        """
        super(DataStream, self).__init__()

    def initialize(self):
        """Delayed stream initialisation code. Subclasses might override this
        method to implement file or handle opening, connecting to a database,
        doing web authentication, ... By default this method does nothing.

        The method does not take any arguments, it expects pre-configured
        object.
        """
        pass

    def finalize(self):
        """Subclasses might put finalisation code here, for example:

        * closing a file stream
        * sending data over network
        * writing a chart image to a file

        Default implementation does nothing.
        """
        pass

    # Context management
    #
    # See: http://docs.python.org/reference/datamodel.html#context-managers
    #
    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.finalize()

class DataSource(DataStream):
    """Input data stream - for reading."""

    def __init__(self):
        """Abstrac class for data sources."""
        super(DataSource, self).__init__()

    def rows(self):
        """Return iterable object with tuples. This is one of two methods for reading from
        data source. Subclasses should implement this method.
        """
        raise NotImplementedError()

    def records(self):
        """Return iterable object with dict objects. This is one of two methods for reading from
        data source. Subclasses should implement this method.
        """
        raise NotImplementedError()

    def read_fields(self, limit = 0, collapse = False):
        """Read field descriptions from data source. You should use this for datasets that do not
        provide metadata directly, such as CSV files, document bases databases or directories with
        structured files. Does nothing in relational databases, as fields are represented by table
        columns and table metadata can obtained from database easily.

        Note that this method can be quite costly, as by default all records within dataset are read
        and analysed.

        After executing this method, stream ``fields`` is set to the newly read field list and may
        be configured (set more appropriate data types for example).

        :Arguments:
            - `limit`: read only specified number of records from dataset to guess field properties
            - `collapse`: whether records are collapsed into flat structure or not

        Returns: tuple with Field objects. Order of fields is datastore adapter specific.
        """

        keys = []
        probes = {}

        def probe_record(record, parent = None):
            for key, value in record.items():
                full_key = parent + "." + key if parent else key

                if self.expand and type(value) == dict:
                    probe_record(value, full_key)
                    continue

                if not full_key in probes:
                    probe = brewery.dq.FieldTypeProbe(full_key)
                    probes[full_key] = probe
                    keys.append(full_key)
                else:
                    probe = probes[full_key]
                probe.probe(value)

        count = 0
        for record in self.records():
            if collapse:
                record = collapse_record(record)

            probe_record(record)
            if limit and count >= limit:
                break
            count += 1

        fields = []

        for key in keys:
            probe = probes[key]
            field = Field(probe.field)

            storage_type = probe.unique_storage_type
            if not storage_type:
                field.storage_type = "unknown"
            elif storage_type == "unicode":
                field.storage_type = "string"
            else:
                field.storage_type = "unknown"
                field.concrete_storage_type = storage_type

            # FIXME: Set analytical type

            fields.append(field)

        self.fields = list(fields)
        return self.fields

class DataTarget(DataStream):
    """Output data stream - for writing.
    """
    def __init__(self):
        """Abstrac class for data targets."""
        super(DataTarget, self).__init__()

    def append(self, object):
        """Append an object into dataset. Object can be a tuple, array or a dict object. If tuple
        or array is used, then value position should correspond to field position in the field list,
        if dict is used, the keys should be valid field names.
        """
        raise NotImplementedError()

