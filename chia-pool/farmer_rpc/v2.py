from __future__ import annotations

from api.farmer_protocols.v2.farmer import (
    FarmerRequest,
    GetFarmerRequest,
    GetFarmerResponse,
    GetLoginReponse,
    GetLoginRequest,
    GetPoolInfoResponse,
    PostPartialRequest,
)


async def get_login(request: GetLoginRequest) -> GetLoginReponse:
    pass


async def get_farmer(request: GetFarmerRequest) -> GetFarmerResponse:
    pass


async def post_farmer(request: FarmerRequest) -> PostFarmerResponse:
    pass


async def put_farmer(request: FarmerRequest) -> PutFarmerResponse:
    pass


async def get_pool_info(request: None) -> GetPoolInfoResponse:
    pass


async def post_partial(request: PostPartialRequest) -> PostPartialResponse:
    pass
