-- Runs once, when the local Compose database volume is first created.
-- Gives the API tests their own database so they never wipe local development data.
CREATE DATABASE giftai_test OWNER giftai;
