"""
appstoreconnect/resources.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import inspect
import sys
from abc import ABC, abstractmethod


class Resource(ABC):
    relationships = {}

    def __init__(self, data, api):
        self._data = data
        self._api = api

    def __getattr__(self, item):
        if item == "id":
            return self._data.get("id")
        if item in self._data.get("attributes", {}):
            return self._data.get("attributes", {})[item]
        if item in self.relationships:

            def getter():
                # Try to fetch relationship
                nonlocal item
                url = self._data.get("relationships", {})[item]["links"]["related"]
                if self.relationships[item]["multiple"]:
                    return self._api.get_related_resources(full_url=url)
                else:
                    return self._api.get_related_resource(full_url=url)

            return getter

        raise AttributeError("%s has no attributes %s" % (self.type_name, item))

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


# Beta Testers and Groups


class BetaTester(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betatester
    """

    endpoint = "/v1/betaTesters"
    type = "betaTesters"
    attributes = ["email", "firstName", "inviteType", "lastName"]
    relationships = {
        "apps": {"multiple": True},
        "betaGroups": {"multiple": True},
        "builds": {"multiple": True},
    }


class BetaGroup(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betagroup
    """

    endpoint = "/v1/betaGroups"
    type = "betaGroups"
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


class App(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/app
    """

    endpoint = "/v1/apps"
    type = "apps"
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


class PreReleaseVersion(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/preReleaseVersion
    """

    endpoint = "/v1/preReleaseVersions"
    type = "preReleaseVersions"
    attributes = ["platform", "version"]


class BetaAppLocalization(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppLocalization
    """

    endpoint = "/v1/betaAppLocalizations"
    type = "betaAppLocalizations"
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


class Build(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/build
    """

    endpoint = "/v1/builds"
    type = "builds"
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


class BuildBetaDetail(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/buildBetaDetail
    """

    endpoint = "/v1/buildBetaDetails"
    type = "buildBetaDetails"


class BetaBuildLocalization(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaBuildLocalization
    """

    endpoint = "/v1/betaBuildLocalizations"
    type = "betaBuildLocalizations"
    attributes = ["locale", "whatsNew"]
    relationships = {
        "build": {"multiple": False},
    }


class BetaAppReviewDetail(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppReviewDetail
    """

    endpoint = "/v1/betaAppReviewDetails"
    type = "betaAppReviewDetails"


class BetaAppReviewSubmission(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/betaAppReviewSubmission
    """

    endpoint = "/v1/betaAppReviewSubmissions"
    type = "betaAppReviewSubmissions"
    attributes = ["betaReviewState"]
    relationships = {
        "build": {"multiple": False},
    }


# Users and Roles


class User(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/user
    """

    endpoint = "/v1/users"
    type = "users"
    attributes = ["allAppsVisible", "provisioningAllowed", "roles"]
    relationships = {
        "visibleApps": {"multiple": True},
    }


class UserInvitation(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/userinvitation
    """

    endpoint = "/v1/userInvitations"


# Provisioning
class BundleId(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/bundleid
    """

    endpoint = "/v1/bundleIds"


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


class Device(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/device
    """

    endpoint = "/v1/devices"
    type = "devices"
    attributes = [
        "deviceClass",
        "model",
        "name",
        "platform",
        "status",
        "udid",
        "addedDate",
    ]


class Profile(Resource):
    """
    https://developer.apple.com/documentation/appstoreconnectapi/profile
    """

    endpoint = "/v1/profiles"


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


# create an index of Resources by type
resources = {}
for name, obj in inspect.getmembers(sys.modules[__name__]):
    if (
        inspect.isclass(obj)
        and issubclass(obj, Resource)
        and hasattr(obj, "type")
        and obj != Resource
    ):
        resources[getattr(obj, "type")] = obj
