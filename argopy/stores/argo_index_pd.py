"""
Argo file index store

Implementations based on pandas
"""

import numpy as np
import pandas as pd
import logging
import gzip

from ..errors import DataNotFound, InvalidDatasetStructure
from ..utilities import check_index_cols, is_indexbox, check_wmo, check_cyc, doc_inherit, to_list
from .argo_index_proto import ArgoIndexStoreProto


log = logging.getLogger("argopy.stores.index")


class indexstore_pandas(ArgoIndexStoreProto):
    """Argo GDAC index store using :class:`pandas.DataFrame` as internal storage format.

    With this store, index and search results are saved as pickle files in cache

    """
    __doc__ += ArgoIndexStoreProto.__doc__

    backend = "pandas"

    ext = "pd"
    """Storage file extension"""

    @doc_inherit
    def load(self, nrows=None, force=False):
        """ Load an Argo-index file content

        Returns
        -------
        :class:`pandas.DataFrame`
        """

        def read_csv(input_file, nrows=None):
            this_table = pd.read_csv(
                input_file, sep=",", index_col=None, header=0, skiprows=8, nrows=nrows
            )
            return this_table

        def csv2index(obj, origin):
            index = read_csv(obj, nrows=nrows)
            check_index_cols(
                index.columns.to_list(),
                convention=self.convention,
            )
            log.debug("Argo index file loaded with pandas read_csv. src='%s'" % origin)
            return index

        if not hasattr(self, "index") or force:
            this_path = self.index_path
            if nrows is not None:
                this_path = this_path + "/local" + "#%i.%s" % (nrows, self.ext)
            else:
                this_path = this_path + "/local.%s" % self.ext

            if self.cache and self.fs["client"].exists(this_path):  # and self._same_origin(this_path):
                log.debug(
                    "Index already in memory as pandas table, loading... src='%s'"
                    % (this_path)
                )
                self.index = self._read(self.fs["client"].fs, this_path, fmt=self.ext)
                self.index_path_cache = this_path
            else:
                log.debug("Load index from scratch ...")
                if self.fs["src"].exists(self.index_path + ".gz"):
                    with self.fs["src"].open(self.index_path + ".gz", "rb") as fg:
                        with gzip.open(fg) as f:
                            self.index = csv2index(f, self.index_path + ".gz")
                else:
                    with self.fs["src"].open(self.index_path, "rb") as f:
                        self.index = csv2index(f, self.index_path)

                if self.cache and self.index.shape[0] > 0:
                    self._write(self.fs["client"], this_path, self.index, fmt=self.ext)
                    self.index = self._read(self.fs["client"].fs, this_path, fmt=self.ext)
                    self.index_path_cache = this_path
                    log.debug(
                        "Index saved in cache as pandas table. dest='%s'"
                        % this_path
                    )

        if self.N_RECORDS == 0:
            raise DataNotFound("No data found in the index")
        elif nrows is not None and self.N_RECORDS != nrows:
            self.index = self.index[0: nrows - 1]

        return self

    def run(self, nrows=None):
        """ Filter index with search criteria """
        this_path = self.search_path
        if nrows is not None:
            this_path = this_path + "/local" + "#%i.%s" % (nrows, self.ext)
        else:
            this_path = this_path + "/local.%s" % self.ext

        if self.cache and self.fs["client"].exists(this_path):  # and self._same_origin(this_path):
            log.debug(
                "Search results already in memory as pandas dataframe, loading... src='%s'"
                % (this_path)
            )
            self.search = self._read(self.fs["client"].fs, this_path, fmt=self.ext)
            self.search_path_cache.commit(this_path)
        else:
            log.debug("Compute search from scratch ... ")
            this_filter = np.nonzero(self.search_filter)[0]
            n_match = this_filter.shape[0]
            if nrows is not None and n_match > 0:
                self.search = self.index.head(np.min([nrows, n_match])).reset_index()
            else:
                self.search = self.index[self.search_filter].reset_index()

            log.debug("Found %i matches" % self.search.shape[0])
            if self.cache and self.search.shape[0] > 0:
                self._write(self.fs["client"], this_path, self.search, fmt=self.ext)
                self.search = self._read(self.fs["client"].fs, this_path, fmt=self.ext)
                self.search_path_cache.commit(this_path)
                log.debug(
                    "Search results saved in cache as pandas dataframe. dest='%s'"
                    % this_path
                )
        return self

    def _to_dataframe(self, nrows=None, index=False):  # noqa: C901
        """ Return search results as dataframe

            If search not triggered, fall back on full index by default. Using index=True force to return the full index.

            This is where we can process the internal dataframe structure for the end user.
            If this processing is long, we can implement caching here.
        """
        if hasattr(self, "search") and not index:
            if self.N_MATCH == 0:
                raise DataNotFound(
                    "No data found in the index corresponding to your search criteria."
                    " Search definition: %s" % self.cname
                )
            else:
                src = "search results"
                df = self.search.copy()
        else:
            src = "full index"
            if not hasattr(self, "index"):
                self.load(nrows=nrows)
            df = self.index.copy()

        return df, src

    @property
    def search_path(self):
        """ Path to search result uri"""
        # return self.host + "/" + self.index_file + "." + self.sha_df
        return self.fs["client"].fs.sep.join([self.host, "%s.%s" % (self.index_file, self.sha_df)])

    @property
    def uri_full_index(self):
        # return ["/".join([self.host, "dac", f]) for f in self.index["file"]]
        sep = self.fs["src"].fs.sep
        return [sep.join([self.host, "dac", f.replace('/', sep)]) for f in self.index["file"]]

    @property
    def uri(self):
        # return ["/".join([self.host, "dac", f]) for f in self.search["file"]]
        # todo Should also modify separator from "f" because it's "/" on the index file,
        # but should be turned to "\" for local file index on Windows. Remains "/" in all others (linux, mac, ftp. http)
        sep = self.fs["src"].fs.sep
        return [sep.join([self.host, "dac", f.replace('/', sep)]) for f in self.search["file"]]

    def read_wmo(self, index=False):
        """ Return list of unique WMOs in search results

        Fall back on full index if search not found

        Returns
        -------
        list(int)
        """
        if hasattr(self, "search") and not index:
            results = self.search["file"].apply(lambda x: int(x.split("/")[1]))
        else:
            results = self.index["file"].apply(lambda x: int(x.split("/")[1]))
        wmo = np.unique(results)
        return wmo

    def read_params(self, index=False):
        if self.convention not in ["argo_bio-profile_index", "argo_synthetic-profile_index"]:
            raise InvalidDatasetStructure("Cannot list parameters in this index (not a BGC profile index)")
        if hasattr(self, "search") and not index:
            df = self.search['parameters']
        else:
            df = self.index['parameters']
        plist = set(df[0].split(" "))
        def fct(row):
            row = row.split(" ")
            [plist.add(v) for v in row]
            return len(row)
        df.map(fct)
        return sorted(list(plist))

    def records_per_wmo(self, index=False):
        """ Return the number of records per unique WMOs in search results

            Fall back on full index if search not found

        Returns
        -------
        dict
        """
        ulist = self.read_wmo()
        count = {}
        for wmo in ulist:
            if hasattr(self, "search") and not index:
                search_filter = self.search["file"].str.contains(
                    "/%i/" % wmo, regex=True, case=False
                )
                count[wmo] = self.search[search_filter].shape[0]
            else:
                search_filter = self.index["file"].str.contains(
                    "/%i/" % wmo, regex=True, case=False
                )
                count[wmo] = self.index[search_filter].shape[0]
        return count

    def search_wmo(self, WMOs, nrows=None):
        WMOs = check_wmo(WMOs)  # Check and return a valid list of WMOs
        log.debug(
            "Argo index searching for WMOs=[%s] ..."
            % ";".join([str(wmo) for wmo in WMOs])
        )
        self.load()
        self.search_type = {"WMO": WMOs}
        filt = []
        for wmo in WMOs:
            filt.append(
                self.index["file"].str.contains("/%i/" % wmo, regex=True, case=False)
            )
        self.search_filter = np.logical_or.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_cyc(self, CYCs, nrows=None):
        CYCs = check_cyc(CYCs)  # Check and return a valid list of CYCs
        log.debug(
            "Argo index searching for CYCs=[%s] ..."
            % (";".join([str(cyc) for cyc in CYCs]))
        )
        self.load()
        self.search_type = {"CYC": CYCs}
        filt = []
        for cyc in CYCs:
            if cyc < 1000:
                pattern = "_%0.3d.nc" % (cyc)
            else:
                pattern = "_%0.4d.nc" % (cyc)
            filt.append(
                self.index["file"].str.contains(pattern, regex=True, case=False)
            )
        self.search_filter = np.logical_or.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_wmo_cyc(self, WMOs, CYCs, nrows=None):
        WMOs = check_wmo(WMOs)  # Check and return a valid list of WMOs
        CYCs = check_cyc(CYCs)  # Check and return a valid list of CYCs
        log.debug(
            "Argo index searching for WMOs=[%s] and CYCs=[%s] ..."
            % (
                ";".join([str(wmo) for wmo in WMOs]),
                ";".join([str(cyc) for cyc in CYCs]),
            )
        )
        self.load()
        self.search_type = {"WMO": WMOs, "CYC": CYCs}
        filt = []
        for wmo in WMOs:
            for cyc in CYCs:
                if cyc < 1000:
                    pattern = "%i_%0.3d.nc" % (wmo, cyc)
                else:
                    pattern = "%i_%0.4d.nc" % (wmo, cyc)
                filt.append(
                    self.index["file"].str.contains(pattern, regex=True, case=False)
                )
        self.search_filter = np.logical_or.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_tim(self, BOX, nrows=None):
        is_indexbox(BOX)
        log.debug("Argo index searching for time in BOX=%s ..." % BOX)
        self.load()
        self.search_type = {"BOX": BOX}
        tim_min = int(pd.to_datetime(BOX[4]).strftime("%Y%m%d%H%M%S"))
        tim_max = int(pd.to_datetime(BOX[5]).strftime("%Y%m%d%H%M%S"))
        filt = []
        filt.append(self.index["date"].ge(tim_min))
        filt.append(self.index["date"].le(tim_max))
        self.search_filter = np.logical_and.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_lat_lon(self, BOX, nrows=None):
        is_indexbox(BOX)
        log.debug("Argo index searching for lat/lon in BOX=%s ..." % BOX)
        self.load()
        self.search_type = {"BOX": BOX}
        filt = []
        filt.append(self.index["longitude"].ge(BOX[0]))
        filt.append(self.index["longitude"].le(BOX[1]))
        filt.append(self.index["latitude"].ge(BOX[2]))
        filt.append(self.index["latitude"].le(BOX[3]))
        self.search_filter = np.logical_and.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_lat_lon_tim(self, BOX, nrows=None):
        is_indexbox(BOX)
        log.debug("Argo index searching for lat/lon/time in BOX=%s ..." % BOX)
        self.load()
        self.search_type = {"BOX": BOX}
        tim_min = int(pd.to_datetime(BOX[4]).strftime("%Y%m%d%H%M%S"))
        tim_max = int(pd.to_datetime(BOX[5]).strftime("%Y%m%d%H%M%S"))
        filt = []
        filt.append(self.index["date"].ge(tim_min))
        filt.append(self.index["date"].le(tim_max))
        filt.append(self.index["longitude"].ge(BOX[0]))
        filt.append(self.index["longitude"].le(BOX[1]))
        filt.append(self.index["latitude"].ge(BOX[2]))
        filt.append(self.index["latitude"].le(BOX[3]))
        self.search_filter = np.logical_and.reduce(filt)
        self.run(nrows=nrows)
        return self

    def search_params(self, PARAMs, nrows=None):
        if self.convention not in ["argo_bio-profile_index", "argo_synthetic-profile_index"]:
            raise InvalidDatasetStructure("Cannot search for parameters in this index (not a BGC profile index)")
        log.debug("Argo index searching for parameters in PARAM=%s ..." % PARAMs)
        PARAMs = to_list(PARAMs)  # Make sure we deal with a list
        self.load()
        self.search_type = {"PARAM": PARAMs}
        filt = []
        for param in PARAMs:
            filt.append(
                self.index["parameters"].str.contains("%s" % param, regex=True, case=False)
            )
        self.search_filter = np.logical_and.reduce(filt)
        self.run(nrows=nrows)
        return self

    def to_indexfile(self, outputfile):
        """Save search results on file, following the Argo standard index formats

        Parameters
        ----------
        file: str
            File path to write search results to

        Returns
        -------
        str
        """

        if self.convention == "ar_index_global_prof":
            columns = ['file', 'date', 'latitude', 'longitude', 'ocean', 'profiler_type', 'institution',
                               'date_update']
        elif self.convention in ["argo_bio-profile_index", "argo_synthetic-profile_index"]:
            columns = ['file', 'date', 'latitude', 'longitude', 'ocean', 'profiler_type', 'institution',
                               'parameters', 'parameter_data_mode', 'date_update']

        self.search.to_csv(outputfile, sep=',', index=False, index_label=False,
                      header=False,
                      columns=columns)
        outputfile = self._insert_header(outputfile)

        return outputfile