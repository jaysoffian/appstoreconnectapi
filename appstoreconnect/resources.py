"""
appstoreconnect/resources.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from abc import ABC, abstractmethod
from pprint import pprint


class Resource(ABC):
    relationships = {}

    def __init__(self, data, api):
        # print(self.__class__.__name__)
        # pprint(data)
        self._data = data
        self._api = api

    def __getattr__(self, item):
        if item == "id":
            return self._data.get("id")
        if item in self._data.get("attributes", {}):
            return self._data.get("attributes", {})[item]
        if item in self.relationships:
            data = self._data.get("relationships", {})[item].get("data")
            inclusions = {}
            for d in self._data.get("included", []):
                inclusions.setdefault(d["type"], {})[d["id"]] = d

            def getter():
                print(self.__class__.__name__)
                pprint(self.data)

                # Try to fetch relationship
                url = self._data.get("relationships", {})[item]["links"]["related"]
                if self.relationships[item]["multiple"]:
                    return self._api.get_related_resources(url, self, data, inclusions)
                else:
                    return self._api.get_related_resource(url, data, inclusions)

            return getter

        raise AttributeError("%s has no attribute %s" % (self.type_name, item))

    def __repr__(self):
        return "%s id %s" % (self.type_name, self._data.get("id"))

    def __dir__(self):
        return (
            ["id"]
            + list(self._data.get("attributes", {}).keys())
            + list(self._data.get("relationships", {}).keys())
        )

    @property
    def type_name(self):
        return type(self).__name__

    @property
    @abstractmethod
    def endpoint(self):
        pass


resource_types = {}


def resource_type(name):
    def decorator(cls):
        assert name not in resource_types, "duplicate type name"
        resource_types[name] = cls
        cls.type = name
        return cls

    return decorator


# Beta Testers and Groups


@resource_type("betaTesters")
class BetaTester(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betatester
    """

    endpoint = "/v1/betaTesters"
    attributes = ["email", "firstName", "inviteType", "lastName"]
    relationships = {
        "apps": {"multiple": True},
        "betaGroups": {"multiple": True},
        "builds": {"multiple": True},
    }


@resource_type("betaGroups")
class BetaGroup(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betagroup
    """

    endpoint = "/v1/betaGroups"
    attributes = [
        "isInternalGroup",
        "name",
        "publicLink",
        "publicLinkEnabled",
        "publicLinkId",
        "publicLinkLimit",
        "publicLinkLimitEnabled",
        "createdDate",
    ]
    relationships = {
        "app": {"multiple": False},
        "betaTesters": {"multiple": True},
        "builds": {"multiple": True},
    }


# App Resources


@resource_type("apps")
class App(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/app
    """

    endpoint = "/v1/apps"
    attributes = ["bundleId", "name", "primaryLocale", "sku"]
    relationships = {
        "betaLicenseAgreement": {"multiple": False},
        "preReleaseVersions": {"multiple": True},
        "betaAppLocalizations": {"multiple": True},
        "betaGroups": {"multiple": True},
        "betaTesters": {"multiple": True},
        "builds": {"multiple": True},
        "betaAppReviewDetail": {"multiple": False},
    }


@resource_type("preReleaseVersions")
class PreReleaseVersion(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/preReleaseVersion
    """

    endpoint = "/v1/preReleaseVersions"
    attributes = ["platform", "version"]


@resource_type("betaAppLocalizations")
class BetaAppLocalization(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppLocalization
    """

    endpoint = "/v1/betaAppLocalizations"
    attributes = [
        "description",
        "feedbackEmail",
        "locale",
        "marketingUrl",
        "privacyPolicyUrl",
        "tvOsPrivacyPolicy",
    ]
    relationships = {"app": {"multiple": False}}


@resource_type("appEncryptionDeclarations")
class AppEncryptionDeclaration(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/appEncryptionDeclaration
    """

    endpoint = "/v1/appEncryptionDeclarations"


@resource_type("betaLicenseAgreements")
class BetaLicenseAgreement(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaLicenseAgreement
    """

    endpoint = "/v1/betaLicenseAgreements"


# Build Resources


@resource_type("builds")
class Build(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/build
    """

    endpoint = "/v1/builds"
    relationships = {
        "app": {"multiple": False},
        "appEncryptionDeclaration": {"multiple": False},
        "individualTesters": {"multiple": True},
        "preReleaseVersion": {"multiple": False},
        "betaBuildLocalizations": {"multiple": True},
        "buildBetaDetail": {"multiple": False},
        "betaAppReviewSubmission": {"multiple": False},
        "appStoreVersion": {"multiple": False},
        "icons": {"multiple": True},
    }


@resource_type("buildBetaDetails")
class BuildBetaDetail(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/buildBetaDetail
    """

    endpoint = "/v1/buildBetaDetails"


@resource_type("betaBuildLocalizations")
class BetaBuildLocalization(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaBuildLocalization
    """

    endpoint = "/v1/betaBuildLocalizations"
    attributes = ["locale", "whatsNew"]
    relationships = {
        "build": {"multiple": False},
    }


@resource_type("betaAppReviewDetails")
class BetaAppReviewDetail(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppReviewDetail
    """

    endpoint = "/v1/betaAppReviewDetails"


@resource_type("betaAppReviewSubmissions")
class BetaAppReviewSubmission(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppReviewSubmission
    """

    endpoint = "/v1/betaAppReviewSubmissions"
    attributes = ["betaReviewState"]
    relationships = {
        "build": {"multiple": False},
    }


# Users and Roles


@resource_type("users")
class User(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/user
    """

    endpoint = "/v1/users"
    attributes = ["allAppsVisible", "provisioningAllowed", "roles"]
    relationships = {
        "visibleApps": {"multiple": True},
    }


@resource_type("userInvitations")
class UserInvitation(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/userinvitation
    """

    endpoint = "/v1/userInvitations"


# Provisioning


@resource_type("bundleIds")
class BundleId(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/bundleid
    """

    endpoint = "/v1/bundleIds"


@resource_type("certificates")
class Certificate(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/certificate
    """

    endpoint = "/v1/certificates"
    attributes = [
        "certificateContent",
        "displayName",
        "expirationDate",
        "name",
        "platform",
        "serialNumber",
        "certificateType",
    ]


@resource_type("devices")
class Device(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/device
    """

    endpoint = "/v1/devices"
    attributes = [
        "deviceClass",
        "model",
        "name",
        "platform",
        "status",
        "udid",
        "addedDate",
    ]


@resource_type("profiles")
class Profile(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/profile
    """

    endpoint = "/v1/profiles"
    attributes = [
        "name",
        "platform",
        "profileContent",
        "uuid",
        "createdDate",
        "profileState",
        "profileType",
        "expirationDate",
    ]
    relationships = {
        "certificates": {"multiple": True},
        "devices": {"multiple": True},
        "bundleId": {"multiple": False},
    }


# Reporting


class FinanceReport(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/download_finance_reports
    """

    endpoint = "/v1/financeReports"


class SalesReport(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/download_sales_and_trends_reports
    """

    endpoint = "/v1/salesReports"
