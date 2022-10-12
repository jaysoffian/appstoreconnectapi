#!/usr/bin/env python3

import dataclasses
import json
import re
import sys
import time
from collections import defaultdict

# from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from itertools import chain
from pathlib import Path

import jwt
import requests
from pydantic.dataclasses import dataclass


def jprint(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def debug_log(msg):
    print(msg, file=sys.stderr)


class BearerToken:
    def __init__(self, issuer_id, key_id, key_file):
        self.issuer_id = issuer_id
        self.key_id = key_id
        self.key = Path(key_file).read_bytes()
        self.expires = 0
        self._token = None

    @property
    def token(self):
        now = int(time.time())
        if now > self.expires:
            self.expires = now + 1200
            payload = {
                "iss": self.issuer_id,
                "exp": self.expires,
                "aud": "appstoreconnect-v1",
            }
            headers = {
                "alg": "ES256",
                "kid": self.key_id,
                "typ": "JWT",
            }
            self._token = jwt.encode(payload=payload, key=self.key, headers=headers)
        return self._token

    def __str__(self):
        return self.token

    def __call__(self, req):
        req.headers["Authorization"] = f"Bearer {self}"
        return req


class AppStoreConnectApi:
    """
    A thin API wrapper for the App Store Connect API:

    https://developer.apple.com/documentation/appstoreconnectapi
    """

    base_url = "https://api.appstoreconnect.apple.com"

    def __init__(self, issuer_id, key_id, key_file):
        self.session = requests.Session()
        self.session.auth = BearerToken(issuer_id, key_id, key_file)
        self.debug = False

    def request(self, method, path_or_url, retry=10, **kwargs):
        """
        Make a request using `method` and `path_or_url` retrying on certain failures.
        """
        kwargs.setdefault("timeout", 120)
        url = (
            path_or_url
            if path_or_url.startswith("https://")
            else f"{self.base_url}/{path_or_url.lstrip('/')}"
        )
        # We're not using requests' retry mechanism (via urllb3 Retry class) because we
        # need to regnerate the token after a 429 and the Retry class doesn't provide
        # a way to do that.
        for attempt in range(retry):
            try:
                if self.debug:
                    debug_log(f"{method} {url}")
                resp = self.session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.Timeout:
                pass
            except requests.HTTPError as exc:
                resp = exc.response
                rate_limit_header = resp.headers["X-Rate-Limit"]
                if m := re.search(r"user-hour-rem:(\d+)", rate_limit_header):
                    if not int(m.group(1)) > 0:
                        raise
                if resp.status_code not in (401, 429, 500):
                    raise
        raise requests.exceptions.RetryError("Retry attempts exceeded")

    def get(self, path_or_url, **kwargs):
        """Send GET request and return response."""
        return self.request("GET", path_or_url, **kwargs)

    def post(self, path_or_url, **kwargs):
        """Send POST request and return response"""
        return self.request("POST", path_or_url, **kwargs)

    def patch(self, path_or_url, **kwargs):
        """Send PATCH request and return response"""
        return self.request("PATCH", path_or_url, **kwargs)

    def delete(self, path_or_url, **kwargs):
        """Send DELETE request and return response"""
        return self.request("DELETE", path_or_url, **kwargs)

    @staticmethod
    def fold_included_into_page_data(page):
        """
        Fold included items into page data items.

        When using the "include" query param, the API returns the included items in
        a separate "included" list. Each item in the "data" list has a "relationships"
        key whose value(s) reference the items in the "included" list by their type
        and id. This function replaces those references with the referenced objects.
        """
        if "included" not in page or not isinstance(page["data"], list):
            return

        includes = defaultdict(dict)
        for obj in page["included"]:
            includes[obj["type"]][obj["id"]] = obj

        get_include = lambda obj: includes[obj["type"]][obj["id"]]  # noqa

        for obj in page["data"]:
            for rel in obj["relationships"].values():
                rel_data = rel.get("data", None)
                if isinstance(rel_data, dict):
                    rel["data"] = get_include(rel_data)
                elif isinstance(rel_data, list):
                    rel["data"] = [get_include(o) for o in rel_data]

    def get_data_iter(
        self,
        path_or_url,
        fields=None,
        include=None,
        limit=None,
        **kwargs,
    ):
        """
        Return an iterator which yields data until no more data is available.

        :param path_or_url: see make_full_url
        :param fields: Dictionary of fields to include in data.
        :param include: Sequence of values to include in data.
        :param limit: Maximum number of items to return per iteration. This should
            generally be set either to "1" or to the maximum value allowed by the API.
            If not given, the API returns a default number of items, usually much
            smaller than the maximum allowed per request.

        The App Store Connect API returns data in pages, one page per request. This
        iterator requests a page per iteration until no more pages are available. Each
        page is a JSON object containing "data", "links", and "included" (if "include"
        is not None) fields. The value of "data" (a list containing up to "limit"
        dictionary items) is yielded after folding in the items from "included".
        """
        params = kwargs.setdefault("params", {})
        if fields:
            params.update(
                {f"fields[{key}]": ",".join(val) for key, val in fields.items()}
            )
        if include:
            params["include"] = ",".join(include)
        if limit:
            params["limit"] = limit

        while path_or_url:
            resp = self.get(path_or_url, **kwargs)
            page = resp.json()
            self.fold_included_into_page_data(page)
            path_or_url = page.get("links", {}).get("next")
            kwargs.pop("params", None)  # params included in next link
            yield page["data"]

    def get_data(self, path_or_url, **kwargs):
        """Return data from first page"""
        return next(self.get_data_iter(path_or_url, **kwargs))

    def get_all_data(self, path_or_url, **kwargs):
        """Return data from all pages"""
        return list(chain(*self.get_data_iter(path_or_url, **kwargs)))


class Object:
    """An Object returned by the App Store Connect API"""

    types = {}
    type: str

    class Meta:
        path: str
        limit: str
        create: callable
        update: callable

    @classmethod
    def objectclass(cls, type):
        def decorator(obj):
            obj.type = type
            cls.types[obj.type] = obj
            return dataclass(obj, init=False, repr=False)

        return decorator

    @classmethod
    @property
    def field_names(cls):
        return list(cls.__dataclass_fields__)  # pylint:disable=no-member

    @classmethod
    def load(cls, data):
        if "links" in data and "attributes" in data:
            return cls.types[data["type"]].parse(data)
        return data

    def __init__(self, obj):
        assert self.type == obj["type"]

        self.id = obj["id"]
        self.url = obj["links"]["self"]
        self._obj = obj

        attributes = obj["attributes"]
        relationships = obj.get("relationships", {})

        # pylint:disable=no-member
        for name, field in self.__dataclass_fields__.items():
            if name in attributes:
                value = attributes[name]
                value = field.type(value) if value is not None else value
            elif name in relationships:
                data = relationships[name].get("data")
                if isinstance(data, dict):
                    value = self.load(data)
                elif isinstance(data, list):
                    value = [self.load(obj) for obj in data]
                elif relationships[name].get("meta", {}).get("paging"):
                    value = []
                else:
                    value = None
            else:
                value = None
            setattr(self, name, value)

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id})"

    def asdict(self):
        return dataclasses.asdict(self)

    def asjson(self, **kwargs):
        return json.dumps(self.asdict(), default=str, **kwargs)

    @classmethod
    def get(cls, api, id, **kwargs):
        meta = cls.Meta
        return cls.load(api.get_data(f"{meta.path}/{id}", **kwargs))

    @classmethod
    def all(cls, api, **kwargs):
        meta = cls.Meta
        kwargs.setdefault("limit", meta.limit)
        return [cls.load(obj) for obj in api.get_all_data(meta.path, **kwargs)]

    @classmethod
    def create(cls, api, *args, **kwargs):
        meta = cls.Meta
        data = {"data": meta.create(*args, **kwargs), "type": cls.type}
        resp = api.post(meta.path, json=data)
        return cls.load(resp.json()["data"])

    @classmethod
    def update(cls, api, id, *args, **kwargs):
        meta = cls.Meta
        data = {"data": meta.update(*args, **kwargs), "id": id, "type": cls.type}
        resp = api.patch(f"{meta.path}/{id}", json=data)
        return cls.load(resp.json()["data"])


objectclass = Object.objectclass


class DateTimeString:
    def __init__(self, date_time_string):
        self._dt = datetime.fromisoformat(date_time_string)
        self._str = date_time_string

    def __getattr__(self, name):
        return getattr(self._dt, name)

    def __getstate__(self):
        state = self.__dict__.copy()
        del state["_dt"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._dt = datetime.fromisoformat(self._str)

    def __repr__(self):
        return repr(self._dt)

    def __str__(self):
        return self._str


class StringEnum(Enum):
    _generate_next_value_ = lambda name, *args: name  # noqa
    __str__ = lambda self: self.name  # noqa


# pylint:disable=invalid-enum-extension


class BundleIdPlatform(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/bundleidplatform"
    IOS = auto()
    MAC_OS = auto()
    UNIVERSAL = auto()


class CertificateType(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/certificatetype"
    IOS_DEVELOPMENT = auto()
    IOS_DISTRIBUTION = auto()
    MAC_APP_DISTRIBUTION = auto()
    MAC_INSTALLER_DISTRIBUTION = auto()
    MAC_APP_DEVELOPMENT = auto()
    DEVELOPER_ID_KEXT = auto()
    DEVELOPER_ID_APPLICATION = auto()
    DEVELOPMENT = auto()
    DISTRIBUTION = auto()
    PASS_TYPE_ID = auto()
    PASS_TYPE_ID_WITH_NFC = auto()


class DeviceClass(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/device/attributes"
    APPLE_WATCH = auto()
    IPAD = auto()
    IPHONE = auto()
    IPOD = auto()
    APPLE_TV = auto()
    MAC = auto()


class DeviceStatus(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/device/attributes"
    ENABLED = auto()
    DISABLED = auto()


class ProfileState(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/profile/attributes"
    ACTIVE = auto()
    INVALID = auto()


class ProfileType(StringEnum):
    "https://developer.apple.com/documentation/appstoreconnectapi/profile/attributes"
    IOS_APP_DEVELOPMENT = auto()
    IOS_APP_STORE = auto()
    IOS_APP_ADHOC = auto()
    IOS_APP_INHOUSE = auto()
    MAC_APP_DEVELOPMENT = auto()
    MAC_APP_STORE = auto()
    MAC_APP_DIRECT = auto()
    TVOS_APP_DEVELOPMENT = auto()
    TVOS_APP_STORE = auto()
    TVOS_APP_ADHOC = auto()
    TVOS_APP_INHOUSE = auto()
    MAC_CATALYST_APP_DEVELOPMENT = auto()
    MAC_CATALYST_APP_STORE = auto()
    MAC_CATALYST_APP_DIRECT = auto()


@objectclass("bundleIds")
class BundleId(Object):
    "https://developer.apple.com/documentation/appstoreconnectapi/bundleid"

    class Meta:
        path = "v1/bundleIds"
        limit = 200

    identifier: str
    name: str
    platform: BundleIdPlatform
    seedId: str
    # relationships
    profiles: list[dict]
    bundleIdCapabilities: list[dict]


@objectclass("certificates")
class Certificate(Object):
    "https://developer.apple.com/documentation/appstoreconnectapi/certificate"

    class Meta:
        path = "v1/certificates"
        limit = 200

    certificateContent: str
    displayName: str
    expirationDate: DateTimeString
    name: str
    platform: BundleIdPlatform
    serialNumber: str
    certificateType: CertificateType


@objectclass("devices")
class Device(Object):
    "https://developer.apple.com/documentation/appstoreconnectapi/device"

    class Meta:
        path = "v1/devices"
        limit = 200

        @staticmethod
        def create(name: str, platform: BundleIdPlatform, udid: str):
            return {
                "attributes": {"name": name, "platform": str(platform), "udid": udid},
            }

        @staticmethod
        def update(name: str = None, status: DeviceStatus = None):
            attributes = {}
            if name is not None:
                attributes["name"] = name
            if status is not None:
                attributes["status"] = str(status)
            return {"attributes": attributes}

    deviceClass: DeviceClass
    model: str
    name: str
    platform: BundleIdPlatform
    status: DeviceStatus
    udid: str
    addedDate: DateTimeString


def data_relation(type, id):
    return {"data": {"id": id, "type": type}}


def data_relation_list(type, id_list):
    return {"data": [{"id": id, "type": type} for id in id_list]}


@objectclass("profiles")
class Profile(Object):
    "https://developer.apple.com/documentation/appstoreconnectapi/profile"

    class Meta:
        path = "v1/profiles"
        limit = 200

        @staticmethod
        def create(
            name: str,
            profileType: ProfileType,
            bundleId: str,
            certificate_ids: list[str],
            device_ids: list[str] = None,
            templateName: str = None,
        ):
            if not device_ids:
                device_ids = []
            attributes = {"name": name, "profileType": str(profileType)}
            if templateName:
                attributes["templateName"] = templateName
            return {
                "attributes": attributes,
                "relationships": {
                    "bundleId": data_relation("bundleIds", bundleId),
                    "certificates": data_relation_list("certificates", certificate_ids),
                    "devices": data_relation_list("devices", device_ids),
                },
            }

    name: str
    platform: BundleIdPlatform
    profileContent: str
    uuid: str
    createdDate: DateTimeString
    profileState: ProfileState
    profileType: ProfileType
    expirationDate: DateTimeString
    # relationships
    bundleId: BundleId
    certificates: list[Certificate]
    devices: list[Device]


def auth_kwargs(account="yahoo"):
    home = Path.home()
    keys = home / "Work/code/mobile-tools/appstore-user-cleanup/keys"
    return {
        "aol": dict(
            key_id="H8YNM7Z2ZK",
            key_file=f"{keys}/appstore-aol.key",
            issuer_id="69a6de77-24ca-47e3-e053-5b8c7c11a4d1",
        ),
        "yahoo": dict(
            key_id="HNZHYQX57Z",
            key_file=f"{keys}/appstore-yahoo.key",
            issuer_id="69a6de79-a7da-47e3-e053-5b8c7c11a4d1",
        ),
    }[account]


aol_api = AppStoreConnectApi(**auth_kwargs("aol"))
yahoo_api = AppStoreConnectApi(**auth_kwargs("yahoo"))


def main():
    api = AppStoreConnectApi(**auth_kwargs("yahoo"))
    api.debug = True
    # Fields that we want in the response for each data type. If not specified for
    # a given data type, the API returns all fields.
    fields = {
        "bundleIds": BundleId.field_names,
        "certificates": Certificate.field_names,
        "devices": Device.field_names,
        "profiles": Profile.field_names,
    }
    fields["certificates"].remove("certificateContent")
    fields["profiles"].remove("profileContent")
    include = ("bundleId", "certificates", "devices")

    profiles = Profile.all(api, fields=fields, include=include)
    return api, profiles


if __name__ == "__main__":
    main()
